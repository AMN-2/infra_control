#!/usr/bin/env bash
# Deploy a branch from GitHub to the staging control plane:  deploy.sh [branch]
#
#   1. refuse while an Infra Job is Running (the worker reads files from this checkout)
#   2. git fetch + fast-forward the branch (never a merge, never a reset: a diverged branch stops here)
#   3. pip install -e (new Python deps), bench migrate (DocTypes, scheduled job types)
#   4. build the SPA when frontend/ changed and publish it to infra_control/public/frontend
#   5. restart web + worker through staging.sh (the edge keeps serving during the restart)
#
# Idempotent: running it twice with nothing new fetches, finds no change, and exits 0.
# Used by hand or by .github/workflows/deploy-staging.yml over SSH.
set -euo pipefail

BENCH=${BENCH:-/home/frappe/frappe-bench}
SITE=${INFRA_SITE:-ops-staging.localhost}
APP=$BENCH/apps/infra_control
REMOTE=${DEPLOY_REMOTE:-https://github.com/AMN-2/infra_control.git}
BRANCH=${1:-${DEPLOY_BRANCH:-main}}
BENCH_CLI=${BENCH_CLI:-$(command -v bench || echo "$HOME/venv/bench/bin/bench")}
HERE=$(cd "$(dirname "$0")" && pwd)
export PATH="$HOME/.nvm/versions/node/$(ls "$HOME/.nvm/versions/node" | sort -V | tail -1)/bin:$PATH"

log() { printf '\n== %s\n' "$*"; }

cd "$APP"
log "deploying $BRANCH to $SITE ($(date -u +%FT%TZ))"

running=$("$BENCH_CLI" --site "$SITE" execute frappe.db.count --args '["Infra Job", {"status": "Running"}]' 2>/dev/null | tail -1)
if [ "${running:-0}" != "0" ]; then
	echo "refusing: $running Infra Job(s) Running; try again when they finish"; exit 3
fi
if [ -n "$(git status --porcelain --untracked-files=no -- infra_control contracts deploy frontend/src)" ]; then
	echo "refusing: uncommitted changes in the checkout (commit or stash them first)"; exit 3
fi

log "fetch"
git fetch --quiet "$REMOTE" "$BRANCH"
before=$(git rev-parse HEAD)
target=$(git rev-parse FETCH_HEAD)
# Forward only, across branches too: the remote branch must contain what runs now. This is
# what stopped a "deploy main" from rolling staging back to the scaffold commit (2026-10-08).
if [ "$before" != "$target" ] && ! git merge-base --is-ancestor "$before" "$target"; then
	echo "refusing: origin/$BRANCH ($target) does not contain the deployed commit ($before)."
	echo "          Merge or fast-forward $BRANCH on GitHub first; a rollback is a manual git checkout."
	exit 3
fi
git checkout --quiet -B "$BRANCH" "$target"
after=$(git rev-parse HEAD)
if [ "$before" = "$after" ]; then echo "already at $after; nothing to deploy"; exit 0; fi
echo "$before -> $after"
changed=$(git diff --name-only "$before" "$after")

if grep -q '^pyproject.toml' <<<"$changed"; then
	log "python deps"; "$BENCH/env/bin/pip" install -q -e "$APP[dev]"
fi

log "migrate $SITE"
"$BENCH_CLI" --site "$SITE" migrate 2>&1 | tail -3

if grep -q '^frontend/' <<<"$changed"; then
	log "frontend build"
	cd "$APP/frontend"
	if grep -q '^frontend/package-lock.json' <<<"$changed"; then npm ci --no-audit --no-fund; fi
	INFRA_UI_BASE=/assets/infra_control/frontend/ npm run build 2>&1 | tail -2
	rsync -a --delete --exclude .gitkeep dist/ "$APP/infra_control/public/frontend/"
	"$BENCH_CLI" --site "$SITE" clear-website-cache >/dev/null
	cd "$APP"
fi

log "restart web + worker"
"$HERE/staging.sh" restart web worker
"$HERE/staging.sh" status | sed -n '1,5p'
log "deployed $after"
