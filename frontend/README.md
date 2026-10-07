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
