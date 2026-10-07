import { reactive, readonly } from "vue";
import type { Tone } from "@/design/status";

export interface Toast {
	id: number;
	title: string;
	description?: string;
	tone: Tone;
	/** ms; 0 keeps it until dismissed. */
	timeout: number;
}

const DEFAULT_TIMEOUT_MS = 6000;
const state = reactive<{ items: Toast[] }>({ items: [] });
let nextId = 1;
const timers = new Map<number, ReturnType<typeof setTimeout>>();

export function pushToast(
	input: Omit<Toast, "id" | "timeout" | "tone"> & Partial<Pick<Toast, "tone" | "timeout">>
): number {
	const toast: Toast = { id: nextId++, tone: "neutral", timeout: DEFAULT_TIMEOUT_MS, ...input };
	state.items = [toast, ...state.items].slice(0, 5);
	if (toast.timeout > 0)
		timers.set(
			toast.id,
			setTimeout(() => {
				dismissToast(toast.id);
			}, toast.timeout)
		);
	return toast.id;
}

export function dismissToast(id: number): void {
	clearTimeout(timers.get(id));
	timers.delete(id);
	state.items = state.items.filter((t) => t.id !== id);
}

export function clearToasts(): void {
	for (const t of state.items) clearTimeout(timers.get(t.id));
	timers.clear();
	state.items = [];
}

export const toasts = readonly(state);
