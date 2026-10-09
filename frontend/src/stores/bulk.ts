import { defineStore } from "pinia";
import { ref } from "vue";
import { api } from "@/api/client";
import type { components } from "@/api/schema";
import { onEvent } from "@/realtime";
import { unwrap, useAsyncState } from "./_async";
type S = components["schemas"];
export type BulkOperation = S["BulkOperation"];
export type BulkDetail = S["BulkOperationDetail"];
export type BulkCreateRequest = S["BulkCreateRequest"];
export type BulkPreflight = S["BulkPreflight"];
export type PreflightTarget = S["PreflightTarget"];

export const useBulkStore = defineStore("bulk", () => {
	const items = ref<BulkOperation[]>([]);
	const details = ref<Record<string, BulkDetail>>({});
	const selected = ref<string | null>(null);
	const nextCursor = ref<string | null>(null);
	const { loading, error, run } = useAsyncState();
	const upsert = (row: BulkOperation) => {
		const i = items.value.findIndex((x) => x.name === row.name);
		if (i < 0) items.value.unshift(row);
		else items.value[i] = row;
	};
	async function fetchList(cursor?: string): Promise<void> {
		await run(async () => {
			const page = unwrap(
				await api.GET("/api/method/infra_control.api.bulk.list", {
					params: { query: { limit: 50, cursor } },
				})
			);
			items.value = cursor ? [...items.value, ...page.items] : [...page.items];
			nextCursor.value = page.next_cursor;
			if (!selected.value && items.value[0]) selected.value = items.value[0].name;
		});
	}
	async function fetchDetail(name: string): Promise<void> {
		selected.value = name;
		await run(async () => {
			const row = unwrap(
				await api.GET("/api/method/infra_control.api.bulk.get", {
					params: { query: { bulk: name } },
				})
			);
			details.value[name] = row;
			upsert(row);
		});
	}
	async function create(body: BulkCreateRequest): Promise<string | undefined> {
		return run(async () => {
			const { bulk } = unwrap(
				await api.POST("/api/method/infra_control.api.bulk.create", { body })
			);
			upsert(bulk);
			await fetchDetail(bulk.name);
			return bulk.name;
		});
	}
	/** ADR 0009: read-only checks per target before a rollout is created. */
	async function preflight(body: S["BulkPreflightRequest"]): Promise<BulkPreflight | undefined> {
		return run(async () =>
			unwrap(await api.POST("/api/method/infra_control.api.bulk.preflight", { body }))
		);
	}
	async function action(kind: "pause" | "resume" | "cancel", name: string): Promise<void> {
		await run(async () => {
			const paths = {
				pause: "/api/method/infra_control.api.bulk.pause",
				resume: "/api/method/infra_control.api.bulk.resume",
				cancel: "/api/method/infra_control.api.bulk.cancel",
			} as const;
			const { bulk } = unwrap(await api.POST(paths[kind], { body: { bulk: name } }));
			upsert(bulk);
			await fetchDetail(name);
		});
	}
	let subscribed = false;
	function subscribe(): void {
		if (subscribed) return;
		subscribed = true;
		onEvent("infra:bulk.updated", (e) => {
			const row = items.value.find((x) => x.name === e.bulk);
			if (row)
				Object.assign(row, {
					status: e.status,
					done: e.done,
					total: e.total,
					current_batch: e.current_batch,
				});
			if (selected.value === e.bulk) void fetchDetail(e.bulk);
			else if (!row) void fetchList();
		});
	}
	return {
		items,
		details,
		selected,
		nextCursor,
		loading,
		error,
		fetchList,
		fetchDetail,
		create,
		action,
		subscribe,
		preflight,
	};
});
