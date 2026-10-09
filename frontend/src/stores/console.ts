import { defineStore } from "pinia";
import { ref } from "vue";
import { api } from "@/api/client";
import type { components } from "@/api/schema";
import { unwrap, useAsyncState } from "./_async";

type S = components["schemas"];
export type ConsoleTicket = S["ConsoleTicket"];
export type ConsoleSession = S["ConsoleSession"];
export type ConsoleTranscript = S["ConsoleTranscript"];

/** Web SSH console (ADR 0007): tickets, sessions and transcripts. */
export const useConsoleStore = defineStore("console", () => {
	const sessions = ref<Record<string, ConsoleSession[]>>({});
	const transcripts = ref<Record<string, ConsoleTranscript>>({});
	const { loading, error, run } = useAsyncState();

	async function ticket(server: string): Promise<ConsoleTicket | undefined> {
		return run(async () =>
			unwrap(
				await api.POST("/api/method/infra_control.api.console.ticket", {
					body: { server },
				})
			)
		);
	}
	async function fetchSessions(server: string): Promise<void> {
		await run(async () => {
			const page = unwrap(
				await api.GET("/api/method/infra_control.api.console.sessions", {
					params: { query: { server, limit: 50 } },
				})
			);
			sessions.value[server] = [...page.items];
		});
	}
	async function fetchTranscript(session: string): Promise<ConsoleTranscript | undefined> {
		return run(async () => {
			const t = unwrap(
				await api.GET("/api/method/infra_control.api.console.transcript", {
					params: { query: { session } },
				})
			);
			transcripts.value[session] = t;
			return t;
		});
	}
	return { sessions, transcripts, loading, error, ticket, fetchSessions, fetchTranscript };
});
