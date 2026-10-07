import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { api } from "@/api/client";
import type { components } from "@/api/schema";
import { onEvent } from "@/realtime";
import { unwrap, useAsyncState } from "./_async";

export type Alert = components["schemas"]["Alert"];

/** Alerts list with optimistic acknowledge (the one optimistic action, plan §10.4). */
export const useAlertsStore = defineStore("alerts", () => {
	const items = ref<Alert[]>([]);
	const nextCursor = ref<string | null>(null);
	const { loading, error, run } = useAsyncState();
	const firing = computed(() => items.value.filter((a) => a.status === "firing"));
	const unresolved = computed(() => items.value.filter((a) => a.status !== "resolved"));

	async function fetchList(
		query: { status?: Alert["status"]; severity?: Alert["severity"] } = {},
		cursor?: string
	): Promise<void> {
		await run(async () => {
			const page = unwrap(
				await api.GET("/api/method/infra_control.api.alerts.list", {
					params: { query: { ...query, limit: 50, cursor } },
				})
			);
			items.value = cursor ? [...items.value, ...page.items] : [...page.items];
			nextCursor.value = page.next_cursor;
		});
	}
	async function acknowledge(name: string, user: string): Promise<void> {
		const target = items.value.find((a) => a.name === name);
		if (!target || target.status !== "firing") return;
		const before = { ...target };
		target.status = "acknowledged";
		target.acknowledged_by = user;
		target.acknowledged_at = new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
		const ok = await run(async () => {
			const { alert } = unwrap(
				await api.POST("/api/method/infra_control.api.alerts.ack", {
					body: { alert: name },
				})
			);
			Object.assign(target, alert);
			return true;
		});
		if (!ok) Object.assign(target, before);
	}

	let subscribed = false;
	function subscribe(): void {
		if (subscribed) return;
		subscribed = true;
		// Signature moment (Alerts): a new alert slides in; the event carries ids, the row comes from the API.
		onEvent("infra:alert.fired", () => void fetchList());
		onEvent("infra:alert.resolved", (e) => {
			const a = items.value.find((x) => x.name === e.alert);
			if (a) {
				a.status = "resolved";
				a.resolved_at = new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
			}
		});
	}

	return {
		items,
		nextCursor,
		firing,
		unresolved,
		loading,
		error,
		fetchList,
		acknowledge,
		subscribe,
	};
});
