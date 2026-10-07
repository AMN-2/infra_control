import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { api } from "@/api/client";
import type { components } from "@/api/schema";
import { onEvent } from "@/realtime";
import { unwrap, useAsyncState } from "./_async";

type S = components["schemas"];
export type Job = S["Job"];
export type JobDetail = S["JobDetail"];
export type JobStep = S["JobStep"];
export type JobRunRequest = S["JobRunRequest"];

const LOG_KEEP_CHARS = 256 * 1024;

/** Jobs list, job detail with steps, and the live log per job (chunks from infra:job.log). */
export const useJobsStore = defineStore("jobs", () => {
	const items = ref<Job[]>([]);
	const nextCursor = ref<string | null>(null);
	const details = ref<Record<string, JobDetail>>({});
	/** Masked log text per job, appended from realtime; the terminal subscribes to `logListeners`. */
	const logs = ref<Record<string, string>>({});
	const logListeners = new Map<string, Set<(chunk: string, idx: number) => void>>();
	const { loading, error, run } = useAsyncState();
	const running = computed(() =>
		items.value.filter((j) => j.status === "Running" || j.status === "Queued")
	);

	async function fetchList(
		query: {
			status?: Job["status"];
			target_doctype?: Job["target_doctype"];
			target_name?: string;
			playbook?: string;
		} = {},
		cursor?: string
	): Promise<void> {
		await run(async () => {
			const page = unwrap(
				await api.GET("/api/method/infra_control.api.jobs.list", {
					params: { query: { ...query, limit: 50, cursor } },
				})
			);
			items.value = cursor ? [...items.value, ...page.items] : [...page.items];
			nextCursor.value = page.next_cursor;
		});
	}
	async function fetchDetail(name: string): Promise<JobDetail | undefined> {
		return run(async () => {
			const d = unwrap(
				await api.GET("/api/method/infra_control.api.jobs.get", {
					params: { query: { job: name } },
				})
			);
			details.value[name] = d;
			return d;
		});
	}
	async function runPlaybook(body: JobRunRequest): Promise<Job | undefined> {
		return run(async () => {
			const { job } = unwrap(
				await api.POST("/api/method/infra_control.api.jobs.run", { body })
			);
			items.value = [job, ...items.value.filter((j) => j.name !== job.name)];
			return job;
		});
	}
	async function cancel(name: string): Promise<Job | undefined> {
		return run(async () => {
			const { job } = unwrap(
				await api.POST("/api/method/infra_control.api.jobs.cancel", {
					body: { job: name },
				})
			);
			apply(job);
			return job;
		});
	}
	async function retry(name: string): Promise<Job | undefined> {
		return run(async () => {
			const { job } = unwrap(
				await api.POST("/api/method/infra_control.api.jobs.retry", { body: { job: name } })
			);
			items.value = [job, ...items.value];
			return job;
		});
	}

	function apply(job: Job): void {
		const i = items.value.findIndex((j) => j.name === job.name);
		if (i >= 0) items.value[i] = job;
		const d = details.value[job.name];
		if (d) Object.assign(d, job);
	}
	function onLog(job: string, listener: (chunk: string, idx: number) => void): () => void {
		let set = logListeners.get(job);
		if (!set) {
			set = new Set();
			logListeners.set(job, set);
		}
		set.add(listener);
		return () => {
			set.delete(listener);
		};
	}

	let subscribed = false;
	function subscribe(): void {
		if (subscribed) return;
		subscribed = true;
		onEvent("infra:job.updated", (e) => {
			const item = items.value.find((j) => j.name === e.job);
			if (item) {
				item.status = e.status;
				item.progress = e.progress;
			}
			const d = details.value[e.job];
			if (d) {
				d.status = e.status;
				d.progress = e.progress;
				// Terminal: refetch once for ended_at, error and the created link.
				if (e.status === "Success" || e.status === "Failed" || e.status === "Cancelled")
					void fetchDetail(e.job);
			} else if (!item) {
				// A job we have never seen (another user started it): pull it into the list.
				void fetchDetail(e.job).then((detail) => {
					if (detail && !items.value.some((j) => j.name === detail.name))
						items.value = [detail, ...items.value];
				});
			}
		});
		onEvent("infra:job.step", (e) => {
			const d = details.value[e.job];
			if (!d) return;
			const step = d.steps.find((s) => s.idx === e.idx);
			if (step) step.status = e.status;
			else
				d.steps = [
					...d.steps,
					{
						idx: e.idx,
						title: e.title,
						status: e.status,
						output: "",
						started_at: null,
						ended_at: null,
					},
				].sort((a, b) => a.idx - b.idx);
			d.steps_total = d.steps.length;
			d.steps_done = d.steps.filter(
				(s) => s.status !== "Queued" && s.status !== "Running"
			).length;
		});
		onEvent("infra:job.log", (e) => {
			logs.value[e.job] = ((logs.value[e.job] ?? "") + e.chunk).slice(-LOG_KEEP_CHARS);
			const d = details.value[e.job];
			const step = d?.steps.find((s) => s.idx === e.idx);
			if (step) step.output = (step.output + e.chunk).slice(-LOG_KEEP_CHARS);
			for (const l of logListeners.get(e.job) ?? []) l(e.chunk, e.idx);
		});
	}

	return {
		items,
		nextCursor,
		details,
		logs,
		running,
		loading,
		error,
		fetchList,
		fetchDetail,
		runPlaybook,
		cancel,
		retry,
		onLog,
		subscribe,
	};
});
