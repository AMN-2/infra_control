import { defineStore } from "pinia";
import { ref } from "vue";
import { api } from "@/api/client";
import type { components } from "@/api/schema";
import { unwrap, useAsyncState } from "./_async";

type S = components["schemas"];
export type SecurityPosture = S["SecurityPosture"];
export type SecurityCheck = S["SecurityCheck"];
export type AuditEntry = S["AuditEntry"];

/** Security posture, the 2FA switch and the audit log (A4.1). */
export const useSecurityStore = defineStore("security", () => {
	const posture = ref<SecurityPosture | null>(null);
	const audit = ref<AuditEntry[]>([]);
	const auditCursor = ref<string | null>(null);
	const { loading, error, run } = useAsyncState();
	const saving = ref(false);
	const saveError = ref<string | null>(null);

	async function fetchPosture(): Promise<void> {
		await run(async () => {
			posture.value = unwrap(
				await api.GET("/api/method/infra_control.api.security.posture")
			);
		});
	}
	async function enable2fa(): Promise<boolean> {
		saving.value = true;
		saveError.value = null;
		try {
			unwrap(
				await api.POST("/api/method/infra_control.api.security.enable_2fa", { body: {} })
			);
			await fetchPosture();
			return true;
		} catch (e) {
			saveError.value = e instanceof Error ? e.message : String(e);
			return false;
		} finally {
			saving.value = false;
		}
	}
	async function fetchAudit(
		query: {
			user?: string;
			action?: string;
			target_doctype?: AuditEntry["target"] extends infer T
				? T extends { target_doctype: infer D }
					? D
					: never
				: never;
			target_name?: string;
		} = {},
		cursor?: string
	): Promise<void> {
		await run(async () => {
			const page = unwrap(
				await api.GET("/api/method/infra_control.api.audit.list", {
					params: { query: { ...query, limit: 50, cursor } },
				})
			);
			audit.value = cursor ? [...audit.value, ...page.items] : [...page.items];
			auditCursor.value = page.next_cursor;
		});
	}
	return {
		posture,
		audit,
		auditCursor,
		loading,
		error,
		saving,
		saveError,
		fetchPosture,
		enable2fa,
		fetchAudit,
	};
});
