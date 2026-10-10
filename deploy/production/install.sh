#!/usr/bin/env bash
# Install the Infra Control production controller on a fresh Ubuntu 24.04 (or 22.04) droplet.
#
#   sudo INFRA_SITE=ops.example.com ADMIN_PASSWORD='...' LETSENCRYPT_EMAIL=you@example.com \
#        ALLOW_CIDRS='203.0.113.4/32' ./install.sh
#
# What it builds (docs/runbooks/production_install.md has the full picture):
#   frappe user ─ bench (frappe v15 + infra_control) ─ one site
#   supervisor  ─ gunicorn, socket.io, bench redis, default workers, `infra` worker, console bridge
#   nginx       ─ TLS (Let's Encrypt or self-signed), IP allowlist, /socket.io and /console/ upgrades
#   ufw + fail2ban, MariaDB bound to localhost, controller SSH key, scheduler on
#
# Idempotent: every step checks before it acts, so re-running after a failure continues.
# Nothing here touches managed servers; onboarding them is onboard-server.sh + the runbook.
set -euo pipefail

: "${INFRA_SITE:?set INFRA_SITE to the controller's FQDN (DNS must already point here) or its IP}"
: "${ADMIN_PASSWORD:?set ADMIN_PASSWORD for the site's Administrator}"
APP_REPO=${APP_REPO:-https://github.com/AMN-2/infra_control.git}
APP_BRANCH=${APP_BRANCH:-main}
FRAPPE_BRANCH=${FRAPPE_BRANCH:-version-15}
BENCH_USER=${BENCH_USER:-frappe}
BENCH_DIR=/home/$BENCH_USER/frappe-bench
TLS=${TLS:-letsencrypt}                 # letsencrypt | selfsigned
ALLOW_CIDRS=${ALLOW_CIDRS:-}            # comma-separated; empty = open to the world (2FA then mandatory)
SSH_ALLOW_CIDRS=${SSH_ALLOW_CIDRS:-}    # comma-separated; empty = SSH from anywhere (keys only)
NODE_MAJOR=${NODE_MAJOR:-20}
STATE_DIR=/root/.infra-control
HERE=$(cd "$(dirname "$0")" && pwd)

[ "$(id -u)" = 0 ] || { echo "run as root (sudo)"; exit 2; }
if [ "$TLS" = letsencrypt ] && [ -z "${LETSENCRYPT_EMAIL:-}" ]; then
	echo "TLS=letsencrypt needs LETSENCRYPT_EMAIL (or use TLS=selfsigned for an IP-only controller)"; exit 2
fi
mkdir -p "$STATE_DIR" && chmod 700 "$STATE_DIR"
log() { printf '\n== %s\n' "$*"; }
as_frappe() { sudo -u "$BENCH_USER" -H bash -lc "$*"; }

log "packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q git curl ca-certificates gnupg python3-dev python3-pip python3-venv pipx \
	mariadb-server mariadb-client libmariadb-dev pkg-config redis-server nginx supervisor \
	certbot ufw fail2ban cron openssh-client rsync build-essential
# bench runs its own redis instances under supervisor; the distro service must not hold the binary's defaults
systemctl disable --now redis-server >/dev/null 2>&1 || true

if ! command -v node >/dev/null || [ "$(node -v | cut -c2-3)" -lt "$NODE_MAJOR" ]; then
	log "node $NODE_MAJOR"
	curl -fsSL "https://deb.nodesource.com/setup_${NODE_MAJOR}.x" | bash -
	apt-get install -y -q nodejs
fi
command -v yarn >/dev/null || npm install -g yarn >/dev/null

log "mariadb"
cat > /etc/mysql/mariadb.conf.d/60-frappe.cnf <<'CNF'
[mysqld]
bind-address = 127.0.0.1
character-set-client-handshake = FALSE
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci
innodb-file-format = barracuda
innodb-file-per-table = 1
innodb-large-prefix = 1
innodb_buffer_pool_size = 512M
[mysql]
default-character-set = utf8mb4
CNF
systemctl enable --now mariadb >/dev/null
if [ ! -s "$STATE_DIR/db-root-password" ]; then
	openssl rand -base64 24 | tr -d '/+=' | head -c 32 > "$STATE_DIR/db-root-password"
	chmod 600 "$STATE_DIR/db-root-password"
	DB_ROOT=$(cat "$STATE_DIR/db-root-password")
	mariadb -e "ALTER USER 'root'@'localhost' IDENTIFIED VIA mysql_native_password USING PASSWORD('$DB_ROOT'); FLUSH PRIVILEGES;"
	systemctl restart mariadb
fi
DB_ROOT=$(cat "$STATE_DIR/db-root-password")

log "user $BENCH_USER"
id "$BENCH_USER" >/dev/null 2>&1 || adduser --disabled-password --gecos "" "$BENCH_USER"
install -d -m 700 -o "$BENCH_USER" -g "$BENCH_USER" "/home/$BENCH_USER/.ssh"
if [ ! -f "/home/$BENCH_USER/.ssh/id_ed25519" ]; then
	as_frappe "ssh-keygen -t ed25519 -N '' -C 'infra-control@$INFRA_SITE' -f ~/.ssh/id_ed25519 -q"
fi

# deploy.sh restarts supervisor as the bench user
echo "$BENCH_USER ALL=(root) NOPASSWD: /usr/bin/supervisorctl" > /etc/sudoers.d/90-infra-control && chmod 440 /etc/sudoers.d/90-infra-control

log "bench"
as_frappe "pipx install frappe-bench >/dev/null 2>&1 || pipx upgrade frappe-bench >/dev/null"
if [ ! -d "$BENCH_DIR/apps/frappe" ]; then
	as_frappe "export PATH=\$HOME/.local/bin:\$PATH && cd ~ && bench init --frappe-branch $FRAPPE_BRANCH --skip-redis-config-generation frappe-bench"
fi
as_frappe "export PATH=\$HOME/.local/bin:\$PATH && cd $BENCH_DIR && bench setup redis >/dev/null"
if [ ! -d "$BENCH_DIR/apps/infra_control" ]; then
	as_frappe "export PATH=\$HOME/.local/bin:\$PATH && cd $BENCH_DIR && bench get-app --branch $APP_BRANCH infra_control $APP_REPO"
fi
if [ ! -d "$BENCH_DIR/sites/$INFRA_SITE" ]; then
	as_frappe "export PATH=\$HOME/.local/bin:\$PATH && cd $BENCH_DIR && bench new-site $INFRA_SITE --db-root-password '$DB_ROOT' --admin-password '$ADMIN_PASSWORD' --install-app infra_control"
fi
as_frappe "export PATH=\$HOME/.local/bin:\$PATH && cd $BENCH_DIR && bench use $INFRA_SITE && bench set-config -g workers '{\"infra\": {\"timeout\": 21600}}' -p \
	&& bench --site $INFRA_SITE set-config infra_ssh_private_key /home/$BENCH_USER/.ssh/id_ed25519 \
	&& bench --site $INFRA_SITE scheduler enable >/dev/null"

log "frontend build"
as_frappe "export PATH=\$HOME/.local/bin:\$PATH && cd $BENCH_DIR/apps/infra_control/frontend && npm ci --no-audit --no-fund >/dev/null \
	&& INFRA_UI_BASE=/assets/infra_control/frontend/ npm run build >/dev/null \
	&& rsync -a --delete --exclude .gitkeep dist/ ../infra_control/public/frontend/ \
	&& cd $BENCH_DIR && bench build --app infra_control >/dev/null 2>&1 || true \
	&& bench --site $INFRA_SITE clear-website-cache >/dev/null"

log "supervisor"
as_frappe "export PATH=\$HOME/.local/bin:\$PATH && cd $BENCH_DIR && bench setup supervisor --yes >/dev/null"
ln -sf "$BENCH_DIR/config/supervisor.conf" /etc/supervisor/conf.d/frappe-bench.conf
sed -e "s|@BENCH_DIR@|$BENCH_DIR|g" -e "s|@BENCH_USER@|$BENCH_USER|g" \
	"$HERE/supervisor-infra.conf.tmpl" > /etc/supervisor/conf.d/infra-control.conf
supervisorctl reread >/dev/null && supervisorctl update >/dev/null
supervisorctl restart all >/dev/null || true

log "nginx + tls ($TLS)"
mkdir -p /var/www/letsencrypt
allow_block=""
if [ -n "$ALLOW_CIDRS" ]; then
	for cidr in ${ALLOW_CIDRS//,/ }; do allow_block+="    allow $cidr;"$'\n'; done
	allow_block+="    deny all;"
fi
render_nginx() {
	sed -e "s|@SITE@|$INFRA_SITE|g" -e "s|@BENCH_DIR@|$BENCH_DIR|g" -e "s|@CERT@|$1|g" -e "s|@KEY@|$2|g" \
		"$HERE/nginx-site.conf.tmpl" | awk -v block="$allow_block" '{ if ($0 ~ /^@ALLOWLIST@$/) print block; else print }' \
		> /etc/nginx/sites-available/infra-control
	ln -sf /etc/nginx/sites-available/infra-control /etc/nginx/sites-enabled/infra-control
	rm -f /etc/nginx/sites-enabled/default
}
if [ "$TLS" = letsencrypt ]; then
	if [ ! -f "/etc/letsencrypt/live/$INFRA_SITE/fullchain.pem" ]; then
		# a temporary http-only server answers the ACME challenge
		cat > /etc/nginx/sites-available/infra-control <<ACME
server { listen 80; server_name $INFRA_SITE; location /.well-known/acme-challenge/ { root /var/www/letsencrypt; } location / { return 503; } }
ACME
		ln -sf /etc/nginx/sites-available/infra-control /etc/nginx/sites-enabled/infra-control
		rm -f /etc/nginx/sites-enabled/default
		nginx -t && systemctl reload nginx
		certbot certonly --webroot -w /var/www/letsencrypt -d "$INFRA_SITE" -m "$LETSENCRYPT_EMAIL" --agree-tos --non-interactive
	fi
	render_nginx "/etc/letsencrypt/live/$INFRA_SITE/fullchain.pem" "/etc/letsencrypt/live/$INFRA_SITE/privkey.pem"
	# certbot's renewal reloads nginx
	printf '#!/bin/sh\nsystemctl reload nginx\n' > /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
	chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
else
	if [ ! -f "$STATE_DIR/tls/cert.pem" ]; then
		mkdir -p "$STATE_DIR/tls"
		san="DNS:$INFRA_SITE"; [[ $INFRA_SITE =~ ^[0-9.]+$ ]] && san="IP:$INFRA_SITE"
		openssl req -x509 -newkey rsa:2048 -nodes -days 730 -subj "/CN=$INFRA_SITE/O=Infra Control" \
			-addext "subjectAltName=$san" -keyout "$STATE_DIR/tls/key.pem" -out "$STATE_DIR/tls/cert.pem" 2>/dev/null
		chmod 600 "$STATE_DIR/tls/key.pem"
	fi
	render_nginx "$STATE_DIR/tls/cert.pem" "$STATE_DIR/tls/key.pem"
fi
nginx -t && systemctl enable --now nginx >/dev/null && systemctl reload nginx

log "firewall"
ufw --force reset >/dev/null
ufw default deny incoming >/dev/null && ufw default allow outgoing >/dev/null
if [ -n "$SSH_ALLOW_CIDRS" ]; then
	for cidr in ${SSH_ALLOW_CIDRS//,/ }; do ufw allow from "$cidr" to any port 22 proto tcp >/dev/null; done
else
	ufw allow 22/tcp >/dev/null
fi
ufw allow 80/tcp >/dev/null && ufw allow 443/tcp >/dev/null
ufw --force enable >/dev/null
systemctl enable --now fail2ban >/dev/null
cat > /etc/ssh/sshd_config.d/90-infra-control.conf <<'SSHD'
PermitRootLogin prohibit-password
PasswordAuthentication no
KbdInteractiveAuthentication no
X11Forwarding no
SSHD
systemctl restart ssh 2>/dev/null || systemctl restart sshd

PUBLIC_IP=$(curl -4 -s -m 5 https://api.ipify.org || hostname -I | awk '{print $1}')
scheme=https
cat <<SUMMARY

==================================================================
Infra Control is installed.

  URL            $scheme://$INFRA_SITE/infra
  Administrator  password you passed as ADMIN_PASSWORD
  Public IP      $PUBLIC_IP   -> set as Infra Settings → Controller IP
  Controller SSH public key (add to DigitalOcean as a key named "infra-control"):
    $(cat /home/$BENCH_USER/.ssh/id_ed25519.pub)
  DB root password   $STATE_DIR/db-root-password (keep off this host too)
  Allowlist          ${ALLOW_CIDRS:-NONE: enable 2FA before anything else}

Next (docs/runbooks/production_install.md, section 3):
  1. Log in, create the Infra users and roles, enable 2FA from /infra/settings/security.
  2. Infra Settings: Controller IP, Telegram, Spaces, off-site bucket, then Allow production accounts.
  3. Provider Account: DigitalOcean token (custom scopes, production), is_staging = 0.
  4. Onboard servers: new ones from the New server wizard, existing ones with onboard-server.sh.
==================================================================
SUMMARY
