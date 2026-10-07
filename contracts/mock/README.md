# contracts/mock

Agent B develops against this from day one (plan section 6.3).

```bash
cd contracts/mock
npm ci
npm run dev          # Prism on http://localhost:4010 + realtime on ws://localhost:9000
npm run smoke        # what CI runs: every endpoint answers, every scenario event validates
```

## REST mock (Prism)

`npm run mock` serves `../openapi.yaml` on port 4010 with CORS. Responses are the `default`
examples from the spec, so ids are consistent across endpoints (`SRV-0001`, `JOB-00042`,
`demo.smartchoice-iq.com`, ...). Request bodies and query parameters are validated; an invalid
request gets a Prism 422.

- Auth: Prism enforces the spec's security schemes. Send `Authorization: token mock:mock` (any
  value) or a `sid` cookie, otherwise you get the documented 401.
- Force an error response: send `Prefer: code=409` (or `400`, `403`, `404`) and Prism returns that
  response's example, e.g. the `capability_missing` envelope.
- Pick a named example: `Prefer: example=confirmation_required`.
- Point the SPA at it with Vite's dev proxy for `/api` -> `http://localhost:4010`.

## Realtime mock (Socket.IO)

`npm run realtime` starts a Socket.IO server on port 9000 that mirrors Frappe's transport: connect
to `http://localhost:9000/<site>` (any namespace), `path: "/socket.io"`. Events are the
`infra:*` names; payloads are validated against `../events/*.schema.json` before they are sent.

| Scenario | What it shows |
|---|---|
| `provisioning` | `server.provision` on a new server: steps, logs, first heartbeat, `inventory.changed`, success |
| `failing-migrate` | `site.migrate` that backs up, fails on `bench migrate`, skips the rest, fires a critical alert |
| `bulk-rollout` | Bulk migrate: canary, then a batch of two in parallel, `bulk.updated` after every target |
| `bulk-halted` | Bulk migrate whose canary fails: status `Halted`, nothing else runs |
| `alert-flap` | Server goes `Down`, critical alert fires, then recovers and resolves |

Trigger a replay:

```bash
curl -X POST http://localhost:9000/mock/replay/provisioning
curl http://localhost:9000/mock/scenarios
curl -X POST http://localhost:9000/mock/emit -d '{"event":"infra:job.log","payload":{"job":"JOB-00042","idx":2,"chunk":"hello\n"}}'
```

Options: `node realtime.js --loop provisioning` replays forever; `--no-heartbeat` disables the
10-second `server.heartbeat` ticker for `SRV-0001` and `SRV-0002`; `--port 9000`.
