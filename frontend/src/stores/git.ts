import { defineStore } from "pinia";
import { ref } from "vue";
import { api } from "@/api/client";
import type { components } from "@/api/schema";
import { unwrap, useAsyncState } from "./_async";

type S = components["schemas"];
export type GitConnection = S["GitConnection"];
export type GitRepo = S["GitRepo"];
export type GitRef = S["GitRef"];

/** GitHub connections and read-only repository browsing (ADR 0005). Tokens never come back. */
export const useGitStore = defineStore("git", () => {
	const connections = ref<GitConnection[]>([]);
	const loaded = ref(false);
	const { loading, error, run } = useAsyncState();
	const saving = ref(false);
	const saveError = ref<string | null>(null);
	/** Cached refs per `connection:repo`. */
	const refs = ref<Record<string, { repo: GitRepo; items: GitRef[] }>>({});

	async function fetchConnections(): Promise<void> {
		await run(async () => {
			const page = unwrap(await api.GET("/api/method/infra_control.api.git.connections"));
			connections.value = [...page.items];
			loaded.value = true;
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
	async function connect(label: string, token: string): Promise<GitConnection | undefined> {
		return mutate(async () => {
			const { connection } = unwrap(
				await api.POST("/api/method/infra_control.api.git.connect", {
					body: { label, token },
				})
			);
			const i = connections.value.findIndex((c) => c.name === connection.name);
			if (i < 0) connections.value.push(connection);
			else connections.value[i] = connection;
			return connection;
		});
	}
	async function disconnect(name: string): Promise<boolean> {
		const ok = await mutate(async () => {
			unwrap(
				await api.POST("/api/method/infra_control.api.git.disconnect", {
					body: { connection: name },
				})
			);
			return true;
		});
		if (ok) connections.value = connections.value.filter((c) => c.name !== name);
		return ok === true;
	}
	/** One page of repositories; the caller owns paging state. */
	async function searchRepos(
		connection: string,
		query: string,
		page = 1
	): Promise<{ items: GitRepo[]; next_page: number | null }> {
		const result = unwrap(
			await api.GET("/api/method/infra_control.api.git.repos", {
				params: { query: { connection, query: query || undefined, page } },
			})
		);
		return { items: [...result.items], next_page: result.next_page };
	}
	async function fetchRefs(
		connection: string,
		repo: string
	): Promise<{ repo: GitRepo; items: GitRef[] } | undefined> {
		const key = `${connection}:${repo}`;
		if (refs.value[key]) return refs.value[key];
		const result = unwrap(
			await api.GET("/api/method/infra_control.api.git.refs", {
				params: { query: { connection, repo } },
			})
		);
		refs.value[key] = { repo: result.repo, items: [...result.items] };
		return refs.value[key];
	}

	return {
		connections,
		loaded,
		loading,
		error,
		saving,
		saveError,
		refs,
		fetchConnections,
		connect,
		disconnect,
		searchRepos,
		fetchRefs,
	};
});
