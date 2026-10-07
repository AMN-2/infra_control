/**
 * Layered layout for the provider → server → bench → site graph (plan §10.2, ADR 0002).
 *
 * Pure and deterministic: the same topology always yields the same picture, so tests can
 * assert positions and the view can animate between layouts. Columns follow the node type;
 * rows come from a depth-first walk so every subtree is contiguous, leaves take one slot each
 * and a parent sits at the mean of its children. Nodes without a parent (orphans the sync has
 * not linked yet) are placed as extra roots after the providers.
 */
import type { components } from "@/api/schema";
import { spaceUnitPx } from "@/design/tokens";

type S = components["schemas"];
export type Topology = S["Topology"];
export type TopologyNode = S["TopologyNode"];
export type TopologyNodeType = S["TopologyNodeType"];

export const COLUMNS: readonly TopologyNodeType[] = ["provider", "server", "bench", "site"];

/** Sizes in px, on the 4px grid. */
export const NODE_W = 52 * spaceUnitPx;
export const NODE_H = 12 * spaceUnitPx;
export const GAP_X = 16 * spaceUnitPx;
export const GAP_Y = 3 * spaceUnitPx;
const PITCH_Y = NODE_H + GAP_Y;
const PITCH_X = NODE_W + GAP_X;

export interface Point {
	x: number;
	y: number;
}

export interface PositionedNode {
	node: TopologyNode;
	column: number;
	x: number;
	y: number;
}

export interface EdgeGeometry {
	id: string;
	source: string;
	target: string;
	a: Point;
	b: Point;
	/** SVG path, a cubic curve between the two anchors. */
	d: string;
}

export interface TopologyLayout {
	nodes: PositionedNode[];
	edges: EdgeGeometry[];
	byId: ReadonlyMap<string, PositionedNode>;
	/** Children per node id, in row order. */
	children: ReadonlyMap<string, string[]>;
	parents: ReadonlyMap<string, string[]>;
	width: number;
	height: number;
}

export function layoutTopology(topology: Pick<Topology, "nodes" | "edges">): TopologyLayout {
	const nodes = new Map(topology.nodes.map((n) => [n.id, n]));
	const children = new Map<string, string[]>();
	const parents = new Map<string, string[]>();
	for (const e of topology.edges) {
		if (!nodes.has(e.source) || !nodes.has(e.target) || e.source === e.target) continue;
		children.set(e.source, [...(children.get(e.source) ?? []), e.target]);
		parents.set(e.target, [...(parents.get(e.target) ?? []), e.source]);
	}

	const columnOf = (n: TopologyNode): number => Math.max(0, COLUMNS.indexOf(n.type));
	const byLabel = (a: string, b: string): number => {
		const na = nodes.get(a);
		const nb = nodes.get(b);
		return (na?.label ?? a).localeCompare(nb?.label ?? b);
	};

	// Roots: every provider, then any other node nobody points at (in column order, by label).
	const roots = topology.nodes
		.filter((n) => n.type === "provider" || !parents.has(n.id))
		.sort((a, b) => columnOf(a) - columnOf(b) || a.label.localeCompare(b.label))
		.map((n) => n.id);

	const rows = new Map<string, number>();
	let cursor = 0;
	const visiting = new Set<string>();
	function place(id: string): number {
		const known = rows.get(id);
		if (known !== undefined) return known;
		if (visiting.has(id)) return cursor; // cycle guard: the API never sends one, the layout survives one
		visiting.add(id);
		const kids = [...(children.get(id) ?? [])].sort(byLabel);
		let row: number;
		if (kids.length === 0) {
			row = cursor;
			cursor += 1;
		} else {
			const placed = kids.map(place);
			row = placed.reduce((sum, r) => sum + r, 0) / placed.length;
		}
		visiting.delete(id);
		rows.set(id, row);
		return row;
	}
	roots.forEach(place);
	// Anything still unplaced sits inside a cycle; give it its own row.
	for (const n of topology.nodes) {
		if (!rows.has(n.id)) {
			rows.set(n.id, cursor);
			cursor += 1;
		}
	}

	const positioned: PositionedNode[] = topology.nodes.map((n) => {
		const column = columnOf(n);
		return { node: n, column, x: column * PITCH_X, y: (rows.get(n.id) ?? 0) * PITCH_Y };
	});
	positioned.sort((a, b) => a.column - b.column || a.y - b.y);
	const byId = new Map(positioned.map((p) => [p.node.id, p]));

	const edges: EdgeGeometry[] = [];
	for (const e of topology.edges) {
		const s = byId.get(e.source);
		const t = byId.get(e.target);
		if (!s || !t || s === t) continue;
		const a = { x: s.x + NODE_W, y: s.y + NODE_H / 2 };
		const b = { x: t.x, y: t.y + NODE_H / 2 };
		const mx = (a.x + b.x) / 2;
		edges.push({
			id: e.id,
			source: e.source,
			target: e.target,
			a,
			b,
			d: `M${a.x},${a.y} C${mx},${a.y} ${mx},${b.y} ${b.x},${b.y}`,
		});
	}

	const usedColumns = positioned.length ? Math.max(...positioned.map((p) => p.column)) + 1 : 0;
	return {
		nodes: positioned,
		edges,
		byId,
		children,
		parents,
		width: usedColumns ? usedColumns * NODE_W + (usedColumns - 1) * GAP_X : 0,
		height: cursor ? cursor * NODE_H + (cursor - 1) * GAP_Y : 0,
	};
}

/**
 * Edges a heartbeat pulse travels for a server: the edge from its provider and every edge in
 * its subtree (server → benches → sites), in the order the pulse should light them.
 */
export function pulseEdges(layout: TopologyLayout, serverRef: string): EdgeGeometry[] {
	const id = `server:${serverRef}`;
	if (!layout.byId.has(id)) return [];
	const wanted = new Set<string>();
	for (const p of layout.parents.get(id) ?? []) wanted.add(`${p}->${id}`);
	const stack = [id];
	const seen = new Set<string>();
	while (stack.length) {
		const current = stack.pop();
		if (current === undefined || seen.has(current)) continue;
		seen.add(current);
		for (const c of layout.children.get(current) ?? []) {
			wanted.add(`${current}->${c}`);
			stack.push(c);
		}
	}
	return layout.edges.filter((e) => wanted.has(`${e.source}->${e.target}`));
}

/** Where a node links to (plan §10.2: provider and bench nodes filter lists, servers and sites open details). */
export function nodeRoute(node: TopologyNode): { path: string; query?: Record<string, string> } {
	switch (node.type) {
		case "server":
			return { path: `/servers/${encodeURIComponent(node.ref)}` };
		case "site":
			return { path: `/sites/${encodeURIComponent(node.ref)}` };
		case "bench":
			return { path: "/sites", query: { bench: node.ref } };
		case "provider":
			return { path: "/servers", query: { provider_account: node.ref } };
	}
}
