# ADR 0002: the topology is drawn with a deterministic layered layout and plain SVG

Date: 2026-10-07. Status: accepted (single-agent decision, recorded for the reviewer; B2.1).

## Context

Plan section 10.4 mentions Vue Flow as a lazy-loaded dependency for the topology screen. The
graph we draw is not a free-form diagram: it is a forest with exactly four layers
(provider → server → bench → site) delivered by `inventory.topology`, at most a few hundred
nodes (plan open question 1: design for up to 20 servers). Vue Flow brings panning, zooming and
edge rendering, but no layout; a layout engine (dagre or ELK) would be a second dependency, and
the signature moment (a pulse travelling the edges on heartbeat, nodes glowing while a job runs)
needs custom edge and node renderers either way.

## Decision

- `frontend/src/features/topology/layout.ts` computes positions: one column per node type, rows
  from a depth-first walk so every subtree is contiguous, leaves one row each, parents centred
  on their children, orphans appended as roots, cycles tolerated. It is pure, deterministic and
  unit-tested on exact coordinates.
- `TopologyGraph.vue` renders the result: SVG curves for edges beneath absolutely positioned
  node cards built from the design system, panned and zoomed with a single transform on the
  stage (motion rule 4: transform and opacity only). Heartbeat pulses are `motion` animations on
  one circle per edge; the pulse follows the server's provider edge and its subtree, one hop at a
  time, skipped under reduced motion or when the tab is hidden.
- No graph library is added. If a later phase needs free-form or user-arranged diagrams, Vue
  Flow can be adopted then; the layout module stays reusable as its auto-layout.

## Consequences

- The topology chunk stays small (no new dependency) and every colour, duration and easing
  comes from tokens.
- Layout quality is bounded by the algorithm: siblings are ordered by label and long rows do not
  wrap. At 200 nodes the picture is tall rather than wide; panning and fit-to-view handle it,
  and the Phase 4 performance pass (B4.1) measures it.
- The plan's section 10.4 note about Vue Flow is read as "if a graph library is used, lazy-load
  it", not as a requirement to use one.
