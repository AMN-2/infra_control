# Infra Control UI

Vue 3 + Vite + TypeScript SPA served at `/infra`. Owner: Agent B (plan §7).

```bash
npm ci                 # also links tests/frontend/node_modules
npm run dev            # http://localhost:5173/infra/  (proxies /api to the mock on :4010)
npm run gen:api        # regenerate src/api/schema.d.ts from contracts/openapi.yaml
```

| Check                              | Command                               |
| ---------------------------------- | ------------------------------------- |
| Lint (src + tests)                 | `npm run lint`                        |
| Types                              | `npm run typecheck`                   |
| Unit tests (`tests/frontend/unit`) | `npm test`                            |
| E2E (`tests/frontend/e2e`)         | `npm run test:e2e`                    |
| Format                             | `npm run format:check`                |
| Initial JS budget (250 KB gz)      | `npm run build && npm run check:size` |
| Client matches contract            | `npm run check:api`                   |

Environment:

- `INFRA_API_TARGET`: where the dev server proxies `/api`. The default is the Prism mock at `http://127.0.0.1:4010`. Point it at a bench (`http://127.0.0.1:8000`) to run against the real API.
- `INFRA_UI_BASE`: the asset base for production builds (see `docs/questions/agent-b.md` Q-B2).

Rules that apply here: talk to the backend only through `src/api/client.ts` (generated types), touch the socket only from `src/realtime/`, and take every colour, size, duration and easing from `src/design/`.

## Realtime and stores (B1.3)

- `src/realtime/` is the only module that imports `socket.io-client`. It connects to Frappe's
  Socket.IO namespace `/<site>` on path `/socket.io` with the session cookie, validates every
  payload against `contracts/events` (Ajv, schemas generated into `events.generated.ts` by
  `npm run gen:events`) and dispatches typed events through `onEvent(name, handler)`.
  Invalid payloads are dropped and counted (`realtimeDropped`).
- `src/stores/` holds one Pinia store per feature (session, overview, inventory, jobs, alerts,
  playbooks). Stores fetch through the generated client and update from events; components never
  touch the socket. `alerts.acknowledge` is the only optimistic action.
- Dev: run the mock (`cd contracts/mock && npm run dev`) and `npm run dev` here. `/api` is
  proxied to Prism on :4010 and `/socket.io` to the replay server on :9000; trigger scenarios
  with `POST http://localhost:9000/mock/replay/<name>`.
