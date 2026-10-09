import { defineStore } from "pinia";
import { ref } from "vue";
import { api } from "@/api/client";
import type { components } from "@/api/schema";
import { unwrap, useAsyncState } from "./_async";

type S = components["schemas"];
export type BackupPolicy = S["BackupPolicy"];
export type BackupPolicyInput = S["BackupPolicyInput"];
export type Backup = S["Backup"];

/** Per-site backup policy and the full backup list (A4.2). */
export const useBackupsStore = defineStore("backups", () => {
	const policies = ref<Record<string, BackupPolicy | null>>({});
	const lists = ref<Record<string, { items: Backup[]; next_cursor: string | null }>>({});
	const { loading, error, run } = useAsyncState();
	const saving = ref(false);
	const saveError = ref<string | null>(null);

	async function fetchPolicy(site: string): Promise<void> {
		await run(async () => {
			const { policy } = unwrap(
				await api.GET("/api/method/infra_control.api.backups.policy", {
					params: { query: { site } },
				})
			);
			policies.value[site] = policy;
		});
	}
	async function savePolicy(input: BackupPolicyInput): Promise<BackupPolicy | undefined> {
		saving.value = true;
		saveError.value = null;
		try {
			const { policy } = unwrap(
				await api.POST("/api/method/infra_control.api.backups.set_policy", { body: input })
			);
			policies.value[input.site] = policy;
			return policy;
		} catch (e) {
			saveError.value = e instanceof Error ? e.message : String(e);
			return undefined;
		} finally {
			saving.value = false;
		}
	}
	async function fetchList(site: string, cursor?: string, kind?: Backup["kind"]): Promise<void> {
		await run(async () => {
			const page = unwrap(
				await api.GET("/api/method/infra_control.api.backups.list", {
					params: { query: { site, kind, limit: 50, cursor } },
				})
			);
			const prev = cursor ? (lists.value[site]?.items ?? []) : [];
			lists.value[site] = { items: [...prev, ...page.items], next_cursor: page.next_cursor };
		});
	}
	return {
		policies,
		lists,
		loading,
		error,
		saving,
		saveError,
		fetchPolicy,
		savePolicy,
		fetchList,
	};
});
