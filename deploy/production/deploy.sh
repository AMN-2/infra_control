#!/usr/bin/env bash
# Update the production controller from GitHub:  deploy.sh [branch]   (run as the bench user)
#
#   1. refuse while an Infra Job is Running or the checkout has local changes
#   2. git fetch + fast-forward only (a diverged branch stops here; rollback is a manual checkout)
#   3. pip install -e when pyproject.toml changed; bench migrate (DocTypes, playbooks, roles)
#   4. rebuild and publish the SPA when frontend/ changed
#   5. supervisorctl restart web, socketio, workers, the infra worker and the console bridge
# Running it with nothing new is a no-op. Same shape as deploy/staging/deploy.sh.
set -euo pipefail

BENCH=${BENCH:-$HOME/frappe-bench}
APP=$BENCH/apps/infra_control
REMOTE=${DEPLOY_REMOTE:-https://github.com/AMN-2/infra_control.git}
BRANCH=${1:-${DEPLOY_BRANCH:-main}}
export PATH="$HOME/.local/bin:$PATH"
SITE=${INFRA_SITE:-$(cat "$BENCH/sites/currentsite.txt")}
STATE=${DEPLOY_STATE:-$HOME/.infra-control/deployed.sha}
mkdir -p "$(dirname "$STATE")"
log() { printf '\n== %s\n' "$*"; }

cd "$APP"
log "deploying $BRANCH to $SITE ($(date -u +%FT%TZ))"
running=$(bench --site "$SITE" execute frappe.db.count --args '["Infra Job", {"status": "Running"}]' 2>/dev/null | tail -1)
if [ "${running:-0}" != "0" ]; then echo "refusing: $running Infra Job(s) Running"; exit 3; fi
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then echo "refusing: local changes in $APP"; exit 3; fi

git fetch --quiet "$REMOTE" "$BRANCH"
head=$(git rev-parse HEAD); before=$(cat "$STATE" 2>/dev/null || echo "$head"); target=$(git rev-parse FETCH_HEAD)
if [ "$head" != "$target" ] && ! git merge-base --is-ancestor "$head" "$target"; then
	echo "refusing: origin/$BRANCH ($target) does not contain the checked-out commit ($head)"; exit 3
fi
git checkout --quiet -B "$BRANCH" "$target"
after=$(git rev-parse HEAD)
if [ "$before" = "$after" ]; then echo "already at $after; nothing to deploy"; exit 0; fi
changed=$(git diff --name-only "$before" "$after")

if grep -q '^pyproject.toml' <<<"$changed"; then log "python deps"; "$BENCH/env/bin/pip" install -q -e "$APP"; fi
log "migrate"; bench --site "$SITE" migrate 2>&1 | tail -3
if grep -q '^frontend/' <<<"$changed"; then
	log "frontend build"
	( cd frontend && { grep -q '^frontend/package-lock.json' <<<"$changed" && npm ci --no-audit --no-fund; true; } \
		&& INFRA_UI_BASE=/assets/infra_control/frontend/ npm run build 2>&1 | tail -2 \
		&& rsync -a --delete --exclude .gitkeep dist/ "$APP/infra_control/public/frontend/" )
	bench --site "$SITE" clear-website-cache >/dev/null
fi
log "restart"
sudo supervisorctl restart all >/dev/null
sudo supervisorctl status | grep -E "RUNNING|FATAL|STOPPED" | awk '{print $1, $2}'
echo "$after" > "$STATE"
log "deployed $after"
