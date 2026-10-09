# ADR 0008: In-app login with a cinematic scene

Date: 2026-10-09. Status: accepted (reviewer request).

## Context

`/infra` rendered only for logged-in users and sent guests to Frappe's `/login`, the shared
website login of the bench (branded by whichever app owns it). The reviewer asked for a login
experience that belongs to Infra Control: a real, calm concert-hall scene (an orchestra
conductor, the orchestration metaphor left unspoken) with the form over it, and a short film
that carries a successful sign-in into the dashboard.

## Decision

1. **Same authentication, same session.** The form posts to Frappe's own `/api/method/login`
   (the request Frappe's page sends) and honours its two-factor step (`verification` +
   `tmp_id`, then `otp`). Nothing in Frappe's auth, cookies or CSRF changes.
2. **One new read endpoint, `session.boot`** (`contracts/openapi.yaml`): the boot record the
   `/infra` page injects (CSRF token, site, user, Infra roles). After Frappe accepts the
   credentials the SPA fetches it, applies it (`session.applyBoot`), starts the authenticated
   services (`app/bootstrap.ts`) and navigates with the router. No page reload. A session
   without an Infra role is refused there (`403 permission_denied`) and the form says so.
3. **`/infra/login` is the guest entry.** `www/infra.py` sends guests to
   `/infra/login?redirect-to=<path>` and renders the SPA with a guest boot record
   (`session_user: "Guest"`, no token, `login_alternatives` when social login or LDAP are
   configured, which link to Frappe's page). The client guard treats the route as `public`
   and bounces signed-in users to the overview. `reauthenticate()` uses the same page.
4. **Redirects are validated.** `safeDestination` accepts only same-origin paths under
   `/infra`, never the login page itself; everything else lands on the overview.
5. **Media never gates sign-in.** `useLoginTransition.ts` is the controller:
   `idle → submitting → (mfa) → authenticated → transitioning → done`. The film starts only
   after the boot confirmed the session. Every wait is bounded (first frame 1.5 s, whole
   transition 4 s), a failed or refused video shortens to a plain fade, reduced motion skips
   the film, and the dashboard route is pushed under the scene so the crossfade lands on real
   UI. The scene lives in `App.vue`, outside the router view, so the route change cannot
   unmount it. A refresh never replays the film.
6. **Assets ship with the bundle** (`frontend/public/media/login`, ~5.5 MB in total,
   MP4 H.264 + WebM VP9, portrait encodes for phones, WebP posters). Provenance, licence and
   the exact FFmpeg commands are in `docs/design/login-media.md`. Masters stay out of the repo.

## Consequences

- Frappe's `/login` keeps working (SSO, LDAP, password reset). Only the Infra entry changes.
- `tests/frontend/unit/login.spec.ts` covers the controller (film only after confirmed auth,
  media failure still navigates, one request and one navigation, two-factor, reduced motion,
  redirect validation); `tests/frontend/e2e/login.spec.ts` drives the real page with Frappe's
  login mocked and `session.boot` from the Prism mock. Backend: `tests/backend/test_login_page.py`.
- The bundled Playwright Chromium has no H.264, so CI exercises the WebM path and the
  "no playable source" fallback; real browsers use the MP4s.
