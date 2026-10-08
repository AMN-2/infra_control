import { defineStore } from "pinia";
import { ref } from "vue";
import { api } from "@/api/client";
import type { components } from "@/api/schema";
import { unwrap, useAsyncState } from "./_async";

type S = components["schemas"];
export type ProviderAccount = S["ProviderAccountSummary"];
export type ProvisionCatalogue = S["ProvisionCatalogue"];
export type ProvisionSize = S["ProvisionSize"];

/** Provider accounts and the per-account provisioning catalogue (ADR 0006). */
export const useProvidersStore = defineStore("providers", () => {
	const accounts = ref<ProviderAccount[]>([]);
	const loaded = ref(false);
	const catalogues = ref<Record<string, ProvisionCatalogue>>({});
	const { loading, error, run } = useAsyncState();

	async function fetchAccounts(): Promise<void> {
		await run(async () => {
			const page = unwrap(await api.GET("/api/method/infra_control.api.providers.accounts"));
			accounts.value = [...page.items];
			loaded.value = true;
		});
	}
	async function fetchCatalogue(account: string): Promise<ProvisionCatalogue | undefined> {
		if (catalogues.value[account]) return catalogues.value[account];
		return run(async () => {
			const data = unwrap(
				await api.GET("/api/method/infra_control.api.providers.options", {
					params: { query: { account } },
				})
			);
			catalogues.value[account] = data;
			return data;
		});
	}
	return { accounts, loaded, catalogues, loading, error, fetchAccounts, fetchCatalogue };
});
