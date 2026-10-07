import { defineStore } from "pinia";
import { ref } from "vue";
import { api } from "@/api/client";
import type { components } from "@/api/schema";
import { unwrap, useAsyncState } from "./_async";

export type Playbook = components["schemas"]["Playbook"];
export type TargetDoctype = components["schemas"]["TargetDoctype"];

/** Actions for a target come from playbooks.list, never from capabilities alone (contract). */
export const usePlaybooksStore = defineStore("playbooks", () => {
	const catalogue = ref<Playbook[]>([]);
	const forTarget = ref<Record<string, Playbook[]>>({});
	const { loading, error, run } = useAsyncState();

	async function fetchAll(): Promise<void> {
		await run(async () => {
			catalogue.value = [
				...unwrap(await api.GET("/api/method/infra_control.api.playbooks.list")).items,
			];
		});
	}
	async function fetchFor(
		target_doctype: TargetDoctype,
		target_name: string
	): Promise<Playbook[]> {
		const key = `${target_doctype}:${target_name}`;
		const items = await run(async () => [
			...unwrap(
				await api.GET("/api/method/infra_control.api.playbooks.list", {
					params: { query: { target_doctype, target_name } },
				})
			).items,
		]);
		forTarget.value[key] = items ?? [];
		return forTarget.value[key] ?? [];
	}

	return { catalogue, forTarget, loading, error, fetchAll, fetchFor };
});
