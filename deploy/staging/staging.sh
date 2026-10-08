#!/usr/bin/env bash
# Staging control plane processes: start | stop | restart | status   (deploy/staging/README.md)
#
#   web     gunicorn for the staging site only, 127.0.0.1:8011, no debugger
#   edge    node edge proxy, 127.0.0.1:8010 (the address you open), routes /socket.io
#   worker  bench worker --queue infra (runs Infra Jobs)
#
# Everything binds to 127.0.0.1; reach it through an SSH / VS Code port forward of 8010.
# Processes are stopped only through their own PID files, never by matching command lines.
set -u

BENCH=${BENCH:-/home/frappe/frappe-bench}
SITE=${INFRA_SITE:-ops-staging.localhost}
HERE=$(cd "$(dirname "$0")" && pwd)
RUN=${RUN_DIR:-$HOME/.infra-staging}
LOGS=$BENCH/logs
NODE=${NODE:-$(ls -d "$HOME"/.nvm/versions/node/v2*/bin/node 2>/dev/null | sort -V | tail -1)}
BENCH_CLI=${BENCH_CLI:-$(command -v bench || echo "$HOME/venv/bench/bin/bench")}
WEB_PORT=${WEB_PORT:-8011}
EDGE_PORT=${EDGE_PORT:-8010}
mkdir -p "$RUN"
# Optional exposure settings (kept out of git): EDGE_HOST, EDGE_PUBLIC, EDGE_ALLOW, EDGE_TLS=1,
# EDGE_TLS_CN. Without the file the edge stays on 127.0.0.1.
[ -f "$RUN/edge.env" ] && . "$RUN/edge.env"
EDGE_HOST=${EDGE_HOST:-127.0.0.1}

tls_pair() {
	# Self-signed certificate for the address in EDGE_TLS_CN (an IP or a host name), 2 years.
	local dir=$RUN/tls cn=${EDGE_TLS_CN:-127.0.0.1} san
	[ -f "$dir/cert.pem" ] && [ -f "$dir/key.pem" ] && return
	mkdir -p "$dir" && chmod 700 "$dir"
	if [[ $cn =~ ^[0-9.]+$ ]]; then san="IP:$cn,IP:127.0.0.1"; else san="DNS:$cn,IP:127.0.0.1"; fi
	openssl req -x509 -newkey rsa:2048 -nodes -days 730 -subj "/CN=$cn/O=Infra Control staging" \
		-addext "subjectAltName=$san" -keyout "$dir/key.pem" -out "$dir/cert.pem" 2>/dev/null
	chmod 600 "$dir/key.pem"
	echo "tls: self-signed certificate for $cn in $dir"
}

alive() { [ -f "$RUN/$1.pid" ] && kill -0 "$(cat "$RUN/$1.pid")" 2>/dev/null; }

start_one() {
	local name=$1; shift
	if alive "$name"; then echo "$name: already running (pid $(cat "$RUN/$name.pid"))"; return; fi
	( cd "$BENCH/sites" && setsid nohup "$@" >>"$LOGS/infra-staging-$name.log" 2>&1 < /dev/null & echo $! > "$RUN/$name.pid" )
	sleep 1
	if alive "$name"; then echo "$name: started (pid $(cat "$RUN/$name.pid"))"; else echo "$name: FAILED, see $LOGS/infra-staging-$name.log"; return 1; fi
}

stop_one() {
	local name=$1
	if ! alive "$name"; then echo "$name: not running"; rm -f "$RUN/$name.pid"; return; fi
	local pid; pid=$(cat "$RUN/$name.pid")
	kill -TERM "$pid"
	for _ in $(seq 1 30); do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
	if kill -0 "$pid" 2>/dev/null; then echo "$name: still running after 30 s (pid $pid), not forcing"; return 1; fi
	rm -f "$RUN/$name.pid"; echo "$name: stopped"
}

start() {
	start_one web "$BENCH/env/bin/gunicorn" --bind "127.0.0.1:$WEB_PORT" --workers 2 --threads 4 \
		--timeout 120 --graceful-timeout 30 --pythonpath "$HERE" --chdir "$BENCH/sites" wsgi:application
	local tls_env=()
	if [ "${EDGE_TLS:-0}" = 1 ]; then
		tls_pair
		tls_env=(EDGE_TLS_CERT="$RUN/tls/cert.pem" EDGE_TLS_KEY="$RUN/tls/key.pem")
	fi
	start_one edge env INFRA_SITE="$SITE" EDGE_HOST="$EDGE_HOST" EDGE_PORT="$EDGE_PORT" \
		EDGE_PUBLIC="${EDGE_PUBLIC:-0}" EDGE_ALLOW="${EDGE_ALLOW:-}" WEB_PORT="$WEB_PORT" \
		"${tls_env[@]}" "$NODE" "$HERE/edge.mjs"
	start_one worker "$BENCH_CLI" worker --queue infra
}

stop() { stop_one edge; stop_one web; stop_one worker; }

status() {
	for name in web edge worker; do
		if alive "$name"; then echo "$name: running (pid $(cat "$RUN/$name.pid"))"; else echo "$name: stopped"; fi
	done
	local scheme=http; [ "${EDGE_TLS:-0}" = 1 ] && scheme=https
	echo "edge  $scheme://$EDGE_HOST:$EDGE_PORT  (allow: ${EDGE_ALLOW:-loopback only})"
	printf "ping through edge -> "
	curl -sk -m 5 "$scheme://127.0.0.1:$EDGE_PORT/api/method/ping" || echo "no answer"
	echo
	printf "realtime through edge -> "
	curl -sk -m 5 "$scheme://127.0.0.1:$EDGE_PORT/socket.io/?EIO=4&transport=polling" | head -c 60 || echo "no answer"
	echo
}

case "${1:-status}" in
	start) start ;;
	stop) stop ;;
	restart) stop; start ;;
	status) status ;;
	*) echo "usage: $0 start|stop|restart|status"; exit 2 ;;
esac
