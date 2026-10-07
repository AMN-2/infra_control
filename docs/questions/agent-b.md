# Open questions — Agent B (Experience)

Per-agent file so the two agents never edit the same table. Agent A keeps its rows in
`docs/questions/agent-a.md`. Add a row when the plan is ambiguous or blocks a task, state the
proposed default and proceed with it unless the reviewer answers otherwise. Answered questions
stay here with the decision.

| # | Date | Raised by | Question | Proposed default | Decision |
|---|---|---|---|---|---|
| Q-B2 | 2026-10-07 | B | How does Frappe serve the SPA at `/infra`? The build output and the page template live in the Python package, which Agent B does not own. | Vite builds to `frontend/dist`. Agent A copies it to `infra_control/public/frontend/` and adds `www/infra.html` plus `website_route_rules` mapping `/infra/<path:app_path>` → `infra`. That page requires login and sets `window.csrf_token`. The frontend then builds with `INFRA_UI_BASE=/assets/infra_control/frontend/`. | **Approved** (2026-10-07). Agent A adds the `/infra` page. The build output path is agreed through the PR handoff note; the default above stands until Agent A proposes otherwise. |
| Q-B4 | 2026-10-07 | B | Should the fonts be self-hosted or loaded from the Google Fonts CDN? | Self-host via `@fontsource-variable` (Space Grotesk, JetBrains Mono). The UI sits behind an IP allowlist/VPN (§13.1) and should make no third-party requests. | **Approved as proposed** (2026-10-07). |
| Q-B5 | 2026-10-07 | B | §10.1 defines only green, amber, red and blue. How should Pending, Provisioning, Queued, Maintenance, Suspended, Archived, Cancelled and Skipped map? | Provisioning/Pending/Queued → blue (in motion or waiting). Maintenance → amber. Suspended/Archived/Cancelled/Skipped → neutral. Broken → red. Details are in `docs/design/tokens.md`. | **Approved as proposed** (2026-10-07). Follow-up: `contracts/openapi.yaml` defines alert `Severity` as `info, warning, critical`; the `info` tone is added when the client is regenerated from the merged contract. |
| Q-B6 | 2026-10-07 | B | §10.1 asks for "one accent colour for actions" without naming it, and it must not read as "blue = running". | A violet-indigo accent, hue-separated from running-blue. Signed off from the `/infra/_design` showcase. | **Approved as proposed** (2026-10-07). |
| Q-B7 | 2026-10-07 | B | Should `/infra/_design` ship in production builds? | Yes, as a lazy chunk with no effect on the initial bundle. Once the auth guard exists (B1.2), it is restricted to `Infra Admin`. | pending |
