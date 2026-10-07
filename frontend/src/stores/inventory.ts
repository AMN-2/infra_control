import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { api } from "@/api/client";
import type { components } from "@/api/schema";
import { onEvent } from "@/realtime";
import { trailing, unwrap, useAsyncState } from "./_async";

type S = components["schemas"];
export type Server = S["Server"];
export type ServerDetail = S["ServerDetail"];
export type Bench = S["Bench"];
export type BenchDetail = S["BenchDetail"];
export type Site = S["Site"];
export type SiteDetail = S["SiteDetail"];
export type Topology = S["Topology"];

/** Servers, benches, sites and the topology, kept fresh by heartbeat and inventory events. */
export const useInventoryStore = defineStore("inventory", () => {
	const servers = ref<Server[]>([]);
	const sites = ref<Site[]>([]);
	const benches = ref<Bench[]>([]);
	const topology = ref<Topology | null>(null);
	const serverDetails = ref<Record<string, ServerDetail>>({});
	const siteDetails = ref<Record<string, SiteDetail>>({});
	const benchDetails = ref<Record<string, BenchDetail>>({});
	const { loading, error, run } = useAsyncState();

	async function fetchServers(
		query: { status?: Server["status"]; provider_account?: string } = {}
	): Promise<void> {
		await run(async () => {
			const page = unwrap(
				await api.GET("/api/method/infra_control.api.servers.list", {
					params: { query: { ...query, limit: 200 } },
				})
			);
			servers.value = [...page.items];
		});
	}
	async function fetchSites(
		query: { status?: Site["status"]; bench?: string; server?: string } = {}
	): Promise<void> {
		await run(async () => {
			const page = unwrap(
				await api.GET("/api/method/infra_control.api.sites.list", {
					params: { query: { ...query, limit: 200 } },
				})
			);
			sites.value = [...page.items];
		});
	}
	async function fetchBenches(
		query: { server?: string; provider_account?: string } = {}
	): Promise<void> {
		await run(async () => {
			const page = unwrap(
				await api.GET("/api/method/infra_control.api.benches.list", {
					params: { query: { ...query, limit: 200 } },
				})
			);
			benches.value = [...page.items];
		});
	}
	async function fetchTopology(): Promise<void> {
		await run(async () => {
			topology.value = unwrap(
				await api.GET("/api/method/infra_control.api.inventory.topology")
			);
		});
	}
	async function fetchServer(name: string): Promise<ServerDetail | undefined> {
		return run(async () => {
			const d = unwrap(
				await api.GET("/api/method/infra_control.api.servers.get", {
					params: { query: { server: name } },
				})
			);
			serverDetails.value[name] = d;
			return d;
		});
	}
	async function fetchSite(name: string): Promise<SiteDetail | undefined> {
		return run(async () => {
			const d = unwrap(
				await api.GET("/api/method/infra_control.api.sites.get", {
					params: { query: { site: name } },
				})
			);
			siteDetails.value[name] = d;
			return d;
		});
	}
	async function fetchBench(name: string): Promise<BenchDetail | undefined> {
		return run(async () => {
			const d = unwrap(
				await api.GET("/api/method/infra_control.api.benches.get", {
					params: { query: { bench: name } },
				})
			);
			benchDetails.value[name] = d;
			return d;
		});
	}

	const serverByName = computed(() => new Map(servers.value.map((s) => [s.name, s])));
	/** Last heartbeat per server, for the topology pulse. */
	const heartbeats = ref<Record<string, { ts: string; cpu: number; ram: number; disk: number }>>(
		{}
	);
	/** The most recent heartbeat, with a sequence so a watcher fires on every beat. */
	const lastBeat = ref<{ server: string; ts: string; seq: number } | null>(null);
	const refetchTopology = trailing(() => void fetchTopology(), 1500);

	let subscribed = false;
	function subscribe(): void {
		if (subscribed) return;
		subscribed = true;
		onEvent("infra:server.heartbeat", (e) => {
			heartbeats.value[e.server] = { ts: e.ts, cpu: e.cpu, ram: e.ram, disk: e.disk };
			lastBeat.value = { server: e.server, ts: e.ts, seq: (lastBeat.value?.seq ?? 0) + 1 };
			const s = serverByName.value.get(e.server);
			if (s) {
				s.status = e.status;
				s.last_heartbeat = e.ts;
			}
			const detail = serverDetails.value[e.server];
			if (detail) {
				detail.status = e.status;
				detail.last_heartbeat = e.ts;
				detail.latest_metrics = {
					ts: e.ts,
					cpu: e.cpu,
					ram: e.ram,
					disk: e.disk,
					load1: detail.latest_metrics?.load1 ?? 0,
					queue_backlog: detail.latest_metrics?.queue_backlog ?? 0,
				};
			}
			const node = topology.value?.nodes.find((n) => n.id === `server:${e.server}`);
			if (node) node.status = e.status;
		});
		onEvent("infra:inventory.changed", (e) => {
			// Refetch the affected collection; the topology always.
			if (e.doctype === "Server") void fetchServers();
			if (e.doctype === "Site") void fetchSites();
			if (e.doctype === "Bench") void fetchBenches();
			void fetchTopology();
		});
		onEvent("infra:job.updated", (e) => {
			if (!topology.value) return;
			// Nodes glow while their job runs (`has_running_job`); the event carries only the job
			// name, so the graph is refreshed once per burst when a job starts or ends.
			if (e.status !== "Running") refetchTopology();
		});
	}

	return {
		servers,
		sites,
		benches,
		topology,
		serverDetails,
		siteDetails,
		benchDetails,
		heartbeats,
		lastBeat,
		loading,
		error,
		fetchServers,
		fetchSites,
		fetchBenches,
		fetchTopology,
		fetchServer,
		fetchSite,
		fetchBench,
		serverByName,
		subscribe,
	};
});
