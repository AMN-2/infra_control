# Building and serving the frontend at `/infra`

Answer to Q-B2. The Vue SPA lives in `frontend/` (Agent B). Frappe serves it through the page
`infra_control/www/infra.{py,html}`; `website_route_rules` in `hooks.py` maps every
`/infra/<path>` to that page, so the SPA router owns all of `/infra/*` (SPA fallback).

## How it fits together

| Piece | Owner | Role |
|---|---|---|
| `frontend/` | B | Vite project, `base` = `INFRA_UI_BASE`, router history base `/infra/` |
| `infra_control/public/frontend/` | A | Copy of `frontend/dist`, served at `/assets/infra_control/frontend/` (git-ignored) |
| `infra_control/core/spa.py` | A | Reads the Vite manifest, resolves entry JS, CSS and preloads |
| `infra_control/www/infra.py` | A | Login required, injects `window.csrf_token` and `window.infra_boot` |

The page is a full HTML document, so Frappe does not wrap it in the website base template.

## Build and publish

```bash
cd apps/infra_control/frontend
npm ci
INFRA_UI_BASE=/assets/infra_control/frontend/ npm run build      # writes frontend/dist (with manifest)

cd ..
rsync -a --delete --exclude .gitkeep frontend/dist/ infra_control/public/frontend/
bench --site <site> clear-website-cache
```

`bench build --app infra_control` is not needed for the SPA itself; Frappe symlinks
`infra_control/public` into `sites/assets/infra_control` on install, so the copied files are
served immediately. The Vite manifest is read on every request (`no_cache = 1`), so a new
build is live without a restart.

## What the page injects

```js
window.csrf_token = "<token>";
window.infra_boot = {
  csrf_token, site_name, session_user,
  roles: ["Infra Admin", "Infra Operator", "Infra Viewer"],   // the user's Infra roles, hierarchy applied
  base_path: "/infra/",
  api_base: "/api/method/infra_control.api.",
  socketio_path: "/socket.io",
  socketio_port: null   // a port number only when `bench serve` renders the page
};
```

Send `X-Frappe-CSRF-Token: window.csrf_token` on every POST.

Realtime: behind nginx (production) the client connects to `/<site>` on the page's own origin and
nginx routes `/socket.io` to Frappe's Socket.IO server. Frappe's dev server has no such route, so
there the page sets `socketio_port` and the client connects to that port on the same host, the
way Frappe's desk does with `window.dev_server`.

## When the bundle is missing

Logged-in users see a plain "Infra Control is not built" page (the reason is shown only in
`developer_mode`) and an Error Log entry is written. Guests are always redirected to
`/login?redirect-to=<path>` first.

## Development

For day-to-day frontend work use `npm run dev` (Vite on :5173, `/api` proxied to the Prism
mock on :4010). The Frappe page is only needed to test the real login, CSRF and asset path.
