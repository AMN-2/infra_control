import { describe, expect, it } from "vitest";
import {
	GAP_Y,
	NODE_H,
	NODE_W,
	GAP_X,
	layoutTopology,
	nodeRoute,
	pulseEdges,
	type TopologyNode,
} from "@/features/topology/layout";

function node(
	type: TopologyNode["type"],
	ref: string,
	extra: Partial<TopologyNode> = {}
): TopologyNode {
	return {
		id: `${type}:${ref}`,
		type,
		ref,
		label: ref,
		status: type === "server" ? "Active" : type === "site" ? "Active" : null,
		provider: "digitalocean",
		has_running_job: false,
		...extra,
	};
}
const edge = (source: string, target: string) => ({ id: `${source}->${target}`, source, target });

const sample = {
	nodes: [
		node("provider", "DO"),
		node("server", "SRV-1", { has_running_job: true }),
		node("server", "SRV-2"),
		node("bench", "B-1"),
		node("site", "a.iq"),
		node("site", "b.iq"),
	],
	edges: [
		edge("provider:DO", "server:SRV-1"),
		edge("provider:DO", "server:SRV-2"),
		edge("server:SRV-1", "bench:B-1"),
		edge("bench:B-1", "site:a.iq"),
		edge("bench:B-1", "site:b.iq"),
	],
};

describe("layoutTopology", () => {
	it("puts each type in its column and centres parents over their children", () => {
		const l = layoutTopology(sample);
		const x = (id: string) => l.byId.get(id)?.x;
		const y = (id: string) => l.byId.get(id)?.y;
		expect(x("provider:DO")).toBe(0);
		expect(x("server:SRV-1")).toBe(NODE_W + GAP_X);
		expect(x("bench:B-1")).toBe(2 * (NODE_W + GAP_X));
		expect(x("site:a.iq")).toBe(3 * (NODE_W + GAP_X));
		// Leaves take one row each; the bench sits between its two sites.
		expect(y("site:a.iq")).toBe(0);
		expect(y("site:b.iq")).toBe(NODE_H + GAP_Y);
		expect(y("bench:B-1")).toBe((NODE_H + GAP_Y) / 2);
		expect(y("server:SRV-1")).toBe(y("bench:B-1"));
		// The leaf server comes after SRV-1's subtree and never overlaps it.
		expect(y("server:SRV-2")).toBe(2 * (NODE_H + GAP_Y));
		expect(l.height).toBe(3 * NODE_H + 2 * GAP_Y);
		expect(l.width).toBe(4 * NODE_W + 3 * GAP_X);
	});

	it("is deterministic and sorts siblings by label", () => {
		const a = layoutTopology(sample);
		const b = layoutTopology({ ...sample, nodes: [...sample.nodes].reverse() });
		expect(a.nodes.map((n) => [n.node.id, n.x, n.y])).toEqual(
			b.nodes.map((n) => [n.node.id, n.x, n.y])
		);
	});

	it("places orphans as extra roots and drops edges to unknown nodes", () => {
		const l = layoutTopology({
			nodes: [node("provider", "DO"), node("site", "lonely.iq")],
			edges: [edge("provider:DO", "server:missing")],
		});
		expect(l.edges).toEqual([]);
		expect(l.byId.get("site:lonely.iq")?.y).toBe(NODE_H + GAP_Y);
		expect(l.byId.get("site:lonely.iq")?.x).toBe(3 * (NODE_W + GAP_X));
	});

	it("survives a cycle without looping forever", () => {
		const l = layoutTopology({
			nodes: [node("server", "A"), node("server", "B")],
			edges: [edge("server:A", "server:B"), edge("server:B", "server:A")],
		});
		expect(l.nodes).toHaveLength(2);
		expect(l.edges).toHaveLength(2);
	});

	it("edges run from the parent's right edge to the child's left edge", () => {
		const l = layoutTopology(sample);
		const e = l.edges.find((x) => x.id === "server:SRV-1->bench:B-1");
		expect(e?.a).toEqual({ x: 2 * NODE_W + GAP_X, y: (NODE_H + GAP_Y) / 2 + NODE_H / 2 });
		expect(e?.b.x).toBe(2 * (NODE_W + GAP_X));
		expect(e?.d.startsWith("M")).toBe(true);
	});

	it("handles an empty topology", () => {
		const l = layoutTopology({ nodes: [], edges: [] });
		expect(l).toMatchObject({ nodes: [], edges: [], width: 0, height: 0 });
	});
});

describe("pulseEdges", () => {
	it("lights the provider edge and the whole subtree of a server, nothing else", () => {
		const l = layoutTopology(sample);
		expect(pulseEdges(l, "SRV-1").map((e) => e.id)).toEqual([
			"provider:DO->server:SRV-1",
			"server:SRV-1->bench:B-1",
			"bench:B-1->site:a.iq",
			"bench:B-1->site:b.iq",
		]);
		expect(pulseEdges(l, "SRV-2").map((e) => e.id)).toEqual(["provider:DO->server:SRV-2"]);
		expect(pulseEdges(l, "nope")).toEqual([]);
	});
});

describe("nodeRoute", () => {
	it("opens details for servers and sites and filters lists for providers and benches", () => {
		expect(nodeRoute(node("server", "SRV-1"))).toEqual({ path: "/servers/SRV-1" });
		expect(nodeRoute(node("site", "a b.iq"))).toEqual({ path: "/sites/a%20b.iq" });
		expect(nodeRoute(node("bench", "B-1"))).toEqual({
			path: "/sites",
			query: { bench: "B-1" },
		});
		expect(nodeRoute(node("provider", "DO"))).toEqual({
			path: "/servers",
			query: { provider_account: "DO" },
		});
	});
});

describe("layoutTopology at scale (B4.1: 200 nodes)", () => {
	/** 2 providers, 20 servers, 40 benches, 138 sites: 200 nodes, 198 edges. */
	function large() {
		const nodes: TopologyNode[] = [];
		const edges: { id: string; source: string; target: string }[] = [];
		let benchIndex = 0;
		for (let p = 0; p < 2; p++) {
			const provider = node("provider", `P-${p}`);
			nodes.push(provider);
			for (let s = 0; s < 10; s++) {
				const server = node("server", `SRV-${p}-${s}`, { has_running_job: s % 7 === 0 });
				nodes.push(server);
				edges.push(edge(provider.id, server.id));
				for (let b = 0; b < 2; b++) {
					const bench = node("bench", `B-${p}-${s}-${b}`);
					nodes.push(bench);
					edges.push(edge(server.id, bench.id));
					const sites = 3 + (benchIndex < 18 ? 1 : 0); // 40 * 3 + 18 = 138
					benchIndex += 1;
					for (let i = 0; i < sites; i++) {
						const site = node("site", `s${p}${s}${b}${i}.iq`);
						nodes.push(site);
						edges.push(edge(bench.id, site.id));
					}
				}
			}
		}
		return { nodes, edges };
	}

	it("places 200 nodes without overlap, in column order, well under a frame budget", () => {
		const topology = large();
		expect(topology.nodes).toHaveLength(200);
		const started = performance.now();
		const layout = layoutTopology(topology);
		const elapsed = performance.now() - started;
		expect(layout.nodes).toHaveLength(200);
		expect(layout.edges).toHaveLength(topology.edges.length);
		expect(elapsed).toBeLessThan(50);

		const columnX = new Map<TopologyNode["type"], number>();
		for (const p of layout.nodes) {
			const x = columnX.get(p.node.type);
			if (x === undefined) columnX.set(p.node.type, p.x);
			else expect(p.x).toBe(x); // one column per type
		}
		const byColumn = new Map<number, number[]>();
		for (const p of layout.nodes) byColumn.set(p.x, [...(byColumn.get(p.x) ?? []), p.y]);
		for (const ys of byColumn.values()) {
			ys.sort((a, b) => a - b);
			for (let i = 1; i < ys.length; i++) {
				expect((ys[i] ?? 0) - (ys[i - 1] ?? 0)).toBeGreaterThanOrEqual(NODE_H);
			}
		}
		expect(layout.width).toBeGreaterThan(0);
		expect(layout.height).toBeGreaterThanOrEqual(138 * NODE_H);
	});

	it("pulses a server's own subtree only, in O(subtree) edges", () => {
		const layout = layoutTopology(large());
		const edges = pulseEdges(layout, "SRV-0-3");
		// provider edge + 2 bench edges + up to 8 site edges
		expect(edges.length).toBeGreaterThanOrEqual(3);
		expect(edges.length).toBeLessThanOrEqual(11);
		expect(edges.every((e) => e.id.includes("SRV-0-3") || e.id.includes("B-0-3-"))).toBe(true);
	});
});
