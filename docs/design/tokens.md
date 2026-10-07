# Design tokens and motion — draft v0 (B0.2)

Live reference: `/infra/_design` (run `cd frontend && npm run dev`, then open
http://localhost:5173/infra/_design). Screenshots: `screenshots/b0.2/`.

## Where things live

| File | Holds |
|---|---|
| `frontend/src/design/tokens.css` | Every colour, type size, space unit, radius, duration and easing, as `--ic-*` CSS variables |
| `frontend/src/design/theme.css` | Maps tokens to Tailwind utilities and removes Tailwind's default palette, easings, shadows and fonts |
| `frontend/src/design/base.css` | Element defaults, the live primitives (`.ic-pulse`, `.ic-glow`), the hover/press `.ic-state-layer`, and `<Transition>` presets |
| `frontend/src/design/motion.ts` | Durations, the one easing, the one spring, presets, the reduced-motion and tab-visibility environment |
| `frontend/src/design/status.ts` | Status → tone mapping for every entity |

## Decisions for review

1. **Accent is violet** (`oklch(0.56 0.19 288)`). It is the only action colour, and it is hue-separated from running-blue so a button never reads as a state (Q-B6). White label on accent: 4.9:1; on hover: 4.6:1.
2. **Status mapping** (Q-B5):

   | Tone | Server | Site | Job / step | Alert |
   |---|---|---|---|---|
   | healthy (green) | Active | Active | Success | |
   | degraded (amber) | Degraded | Maintenance | | warning |
   | down (red) | Down | Broken | Failed | critical |
   | running (blue) | Provisioning | Pending | Queued, Running | |
   | neutral (grey) | Archived | Suspended, Archived | Cancelled, Skipped | |

   Only `Running` and `Provisioning` pulse. Waiting states stay still.
3. **Type:** Space Grotesk (headings, numerals, tabular figures), system UI for body text, and JetBrains Mono for IPs, IDs, paths and logs. Fonts are self-hosted (Q-B4).
4. **Elevation is lightness**, not shadow: canvas plus three surfaces. Only overlays get a shadow.

## Guarantees enforced by tests (`tests/frontend/unit/design-*.spec.ts`)

- All text tokens and status colours meet WCAG AA (4.5:1) on every surface. Accent labels are AA in every state.
- `tokens.css` and `motion.ts` agree on every duration and on the easing. Durations stay within §10.3 limits.
- Reduced motion zeroes every duration, from either the OS setting or the `data-motion="reduce"` override.
- Outside `src/design/`, no hex or colour functions, raw durations, raw easings, Tailwind numeric durations or arbitrary colours appear. Physical CSS (`margin-left`, `ml-*`, `text-left`, …) is also banned: use logical properties.

## Motion contract

| Token | Value | Use |
|---|---|---|
| `--ic-dur-press` | 120 ms | Hover and press feedback |
| `--ic-dur-base` | 200 ms | Most transitions |
| `--ic-dur-emphasis` | 240 ms | Dialogs, panels, shared elements; the spring's visual duration |
| `--ic-dur-scene` | 400 ms | Large scenes; the hard maximum |
| `--ic-ease` | `cubic-bezier(0.2, 0, 0, 1)` | Every enter and exit |
| spring | `visualDuration 0.24, bounce 0.15` | Overlays that should feel physical (palette, dialogs) |

- Only `transform` and `opacity` animate. Hover is a pseudo-element opacity change, glow is a pseudo-element opacity change, and the sparkline draw-in is a transform wipe (`reveal()`).
- Continuous motion (`.ic-pulse`, `.ic-glow`) is reserved for live states. It pauses when the tab is hidden (`<html data-visibility="hidden">`) and stops under reduced motion.
