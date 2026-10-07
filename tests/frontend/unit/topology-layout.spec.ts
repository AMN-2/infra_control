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
