/**
 * Buffers log chunks and flushes them at most every `intervalMs` (plan §10.4: 50 ms) so a
 * burst of `infra:job.log` events never floods the terminal.
 */
export const FLUSH_INTERVAL_MS = 50;

export function createLogBuffer(
	flush: (text: string) => void,
	intervalMs: number = FLUSH_INTERVAL_MS,
	schedule: (fn: () => void, ms: number) => unknown = setTimeout
): { push: (chunk: string) => void; flushNow: () => void; pending: () => number } {
	let buffer = "";
	let scheduled = false;
	const flushNow = (): void => {
		scheduled = false;
		if (!buffer) return;
		const text = buffer;
		buffer = "";
		flush(text);
	};
	return {
		push(chunk) {
			buffer += chunk;
			if (!scheduled) {
				scheduled = true;
				schedule(flushNow, intervalMs);
			}
		},
		flushNow,
		pending: () => buffer.length,
	};
}
