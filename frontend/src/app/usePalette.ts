import { computed, ref } from "vue";
import type { Router } from "vue-router";
import type { components } from "@/api/schema";
import { api } from "@/api/client";
import { navigation } from "./navigation";

export type SearchResult = components["schemas"]["SearchResult"];

export interface PaletteItem {
	id: string;
	group: "Go to" | "Servers" | "Sites" | "Benches" | "Playbooks" | "Jobs" | "Alerts";
	title: string;
	subtitle?: string;
	status?: string | null;
	to: string;
	kbd?: string;
}

const RESULT_ROUTE: Record<SearchResult["type"], (r: SearchResult) => string> = {
	server: (r) => `/servers/${encodeURIComponent(r.id)}`,
	site: (r) => `/sites/${encodeURIComponent(r.id)}`,
	bench: () => "/servers",
	playbook: (r) => `/jobs?playbook=${encodeURIComponent(r.id)}`,
	job: (r) => `/jobs/${encodeURIComponent(r.id)}`,
	alert: () => "/alerts",
};
const GROUP: Record<SearchResult["type"], PaletteItem["group"]> = {
	server: "Servers",
	site: "Sites",
	bench: "Benches",
	playbook: "Playbooks",
	job: "Jobs",
	alert: "Alerts",
};

/** Navigation entries matching the query (client side, instant). */
export function navigationMatches(query: string): PaletteItem[] {
	const q = query.trim().toLowerCase();
	return navigation
		.filter((n) => !q || n.label.toLowerCase().includes(q))
		.map((n) => ({
			id: `nav:${n.name}`,
			group: "Go to",
			title: n.label,
			to: n.to,
			kbd: `g ${n.key}`,
		}));
}

export function toPaletteItem(r: SearchResult): PaletteItem {
	return {
		id: `${r.type}:${r.id}`,
		group: GROUP[r.type],
		title: r.title,
		subtitle: r.subtitle ?? undefined,
		status: r.status,
		to: RESULT_ROUTE[r.type](r),
	};
}

/** Command palette state (Ctrl+K): navigation plus `search.query` results, debounced. */
export function usePalette(router: Router, searchDelayMs = 120) {
	const open = ref(false);
	const query = ref("");
	const remote = ref<PaletteItem[]>([]);
	const active = ref(0);
	const searching = ref(false);
	let timer: ReturnType<typeof setTimeout> | undefined;
	let seq = 0;

	const items = computed<PaletteItem[]>(() => [
		...navigationMatches(query.value),
		...remote.value,
	]);

	async function search(q: string): Promise<void> {
		const mine = ++seq;
		if (!q.trim()) {
			remote.value = [];
			return;
		}
		searching.value = true;
		try {
			const res = await api.GET("/api/method/infra_control.api.search.query", {
				params: { query: { q, limit: 20 } },
			});
			if (mine === seq) remote.value = (res.data?.items ?? []).map(toPaletteItem);
		} catch {
			if (mine === seq) remote.value = [];
		} finally {
			if (mine === seq) searching.value = false;
		}
	}
	function setQuery(q: string): void {
		query.value = q;
		active.value = 0;
		clearTimeout(timer);
		timer = setTimeout(() => void search(q), searchDelayMs);
	}
	function show(): void {
		open.value = true;
		setQuery("");
	}
	function hide(): void {
		open.value = false;
	}
	function toggle(): void {
		if (open.value) hide();
		else show();
	}
	function move(delta: number): void {
		const n = items.value.length;
		if (n) active.value = (active.value + delta + n) % n;
	}
	async function choose(
		item: PaletteItem | undefined = items.value[active.value]
	): Promise<void> {
		if (!item) return;
		hide();
		await router.push(item.to);
	}
	/** Ctrl+K / Cmd+K opens; Escape closes. Installed on the document by the shell. */
	function onKeydown(e: KeyboardEvent): void {
		if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
			e.preventDefault();
			toggle();
		} else if (e.key === "Escape" && open.value) {
			hide();
		}
	}

	return {
		open,
		query,
		items,
		active,
		searching,
		setQuery,
		show,
		hide,
		toggle,
		move,
		choose,
		onKeydown,
	};
}
