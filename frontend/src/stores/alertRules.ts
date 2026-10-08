import { defineStore } from "pinia";
import { ref } from "vue";
import { api } from "@/api/client";
import type { components } from "@/api/schema";
import { unwrap, useAsyncState } from "./_async";

type S = components["schemas"];
export type AlertRule = S["AlertRule"];
export type AlertRuleInput = S["AlertRuleInput"];
export type AlertRuleUpdate = S["AlertRuleUpdate"];

/**
 * Alert rules (B3.2). Only `metric` rules are created or deleted; the built-in kinds are edited
 * within the per-kind field set the contract allows (`AlertRule` description).
 */
export const useAlertRulesStore = defineStore("alertRules", () => {
	const items = ref<AlertRule[]>([]);
	const nextCursor = ref<string | null>(null);
	const { loading, error, run } = useAsyncState();
	const saving = ref(false);
	const saveError = ref<string | null>(null);

	const upsert = (rule: AlertRule) => {
		const i = items.value.findIndex((x) => x.name === rule.name);
		if (i < 0) items.value.push(rule);
		else items.value[i] = rule;
	};

	async function fetchList(cursor?: string): Promise<void> {
		await run(async () => {
			const page = unwrap(
				await api.GET("/api/method/infra_control.api.alert_rules.list", {
					params: { query: { limit: 50, cursor } },
				})
			);
			items.value = cursor ? [...items.value, ...page.items] : [...page.items];
			nextCursor.value = page.next_cursor;
		});
	}

	/** Mutations keep the list's loading/error untouched; the dialog owns `saving`/`saveError`. */
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

	async function create(body: AlertRuleInput): Promise<AlertRule | undefined> {
		return mutate(async () => {
			const { rule } = unwrap(
				await api.POST("/api/method/infra_control.api.alert_rules.create", { body })
			);
			upsert(rule);
			return rule;
		});
	}

	async function update(body: AlertRuleUpdate): Promise<AlertRule | undefined> {
		return mutate(async () => {
			const { rule } = unwrap(
				await api.POST("/api/method/infra_control.api.alert_rules.update", { body })
			);
			upsert(rule);
			return rule;
		});
	}

	/** Enable/disable is optimistic like acknowledge: the switch flips now, rolls back on failure. */
	async function setEnabled(name: string, enabled: boolean): Promise<void> {
		const target = items.value.find((x) => x.name === name);
		if (!target || target.enabled === enabled) return;
		const before = target.enabled;
		target.enabled = enabled;
		const ok = await mutate(async () => {
			const { rule } = unwrap(
				await api.POST("/api/method/infra_control.api.alert_rules.update", {
					body: { rule: name, enabled },
				})
			);
			Object.assign(target, rule);
			return true;
		});
		if (!ok) target.enabled = before;
	}

	async function remove(name: string): Promise<boolean> {
		const ok = await mutate(async () => {
			unwrap(
				await api.POST("/api/method/infra_control.api.alert_rules.delete", {
					body: { rule: name },
				})
			);
			return true;
		});
		if (ok) items.value = items.value.filter((x) => x.name !== name);
		return ok === true;
	}

	return {
		items,
		nextCursor,
		loading,
		error,
		saving,
		saveError,
		fetchList,
		create,
		update,
		setEnabled,
		remove,
	};
});
