import { defineStore } from "pinia";
import { ref } from "vue";
import { api } from "@/api/client";
import type { components } from "@/api/schema";
import { unwrap, useAsyncState } from "./_async";

type S = components["schemas"];
export type Tenant = S["Tenant"];
export type TenantDetail = S["TenantDetail"];

/** Tenants: the client behind sites. */
export const useTenantsStore = defineStore("tenants", () => {
	const items = ref<Tenant[]>([]);
	const nextCursor = ref<string | null>(null);
	const details = ref<Record<string, TenantDetail>>({});
	const { loading, error, run } = useAsyncState();
	const saving = ref(false);
	const saveError = ref<string | null>(null);

	async function fetchList(
		query: { status?: Tenant["status"]; query?: string } = {},
		cursor?: string
	): Promise<void> {
		await run(async () => {
			const page = unwrap(
				await api.GET("/api/method/infra_control.api.tenants.list", {
					params: { query: { ...query, limit: 50, cursor } },
				})
			);
			items.value = cursor ? [...items.value, ...page.items] : [...page.items];
			nextCursor.value = page.next_cursor;
		});
	}
	async function fetchDetail(name: string): Promise<TenantDetail | undefined> {
		return run(async () => {
			const d = unwrap(
				await api.GET("/api/method/infra_control.api.tenants.get", {
					params: { query: { tenant: name } },
				})
			);
			details.value[name] = d;
			return d;
		});
	}
	async function mutate<T>(fn: () => Promise<T>): Promise<T | undefined> {
		saving.value = true;
		saveError.value = null;
		try {
			return await fn();
		} catch (e) {
			saveError.value = e instanceof Error ? e.message : String(e);
			return undefined;
		} finally {
			saving.value = false;
		}
	}
	function remember(d: TenantDetail): void {
		details.value[d.name] = d;
		const i = items.value.findIndex((t) => t.name === d.name);
		const row: Tenant = { ...d, sites: undefined } as unknown as Tenant;
		delete (row as unknown as Record<string, unknown>).sites;
		if (i < 0) items.value.unshift(row);
		else items.value[i] = row;
	}
	async function create(body: {
		label: string;
		title?: string;
		plan?: string;
		contact_email?: string;
		contact_phone?: string;
		notes?: string;
	}): Promise<TenantDetail | undefined> {
		return mutate(async () => {
			const { tenant } = unwrap(
				await api.POST("/api/method/infra_control.api.tenants.create", { body })
			);
			remember(tenant);
			return tenant;
		});
	}
	async function update(body: {
		tenant: string;
		title?: string;
		plan?: string;
		contact_email?: string;
		contact_phone?: string;
		notes?: string;
	}): Promise<TenantDetail | undefined> {
		return mutate(async () => {
			const { tenant } = unwrap(
				await api.POST("/api/method/infra_control.api.tenants.update", { body })
			);
			remember(tenant);
			return tenant;
		});
	}
	async function assign(
		tenant: string,
		site: string,
		remove = false
	): Promise<TenantDetail | undefined> {
		return mutate(async () => {
			const result = unwrap(
				await api.POST("/api/method/infra_control.api.tenants.assign", {
					body: { tenant, site, remove },
				})
			);
			remember(result.tenant);
			return result.tenant;
		});
	}
	async function suspend(
		tenant: string,
		suspended: boolean
	): Promise<{ jobs: string[]; errors: { site: string; error: string }[] } | undefined> {
		return mutate(async () => {
			const result = unwrap(
				await api.POST("/api/method/infra_control.api.tenants.suspend", {
					body: { tenant, suspended },
				})
			);
			remember(result.tenant);
			return { jobs: [...result.jobs], errors: [...result.errors] };
		});
	}
	return {
		items,
		nextCursor,
		details,
		loading,
		error,
		saving,
		saveError,
		fetchList,
		fetchDetail,
		create,
		update,
		assign,
		suspend,
	};
});
