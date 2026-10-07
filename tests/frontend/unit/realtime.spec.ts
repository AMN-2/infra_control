import { beforeEach, describe, expect, it, vi } from "vitest";
import {
	_resetForTests,
	connectRealtime,
	injectEvent,
	onEvent,
	realtimeDropped,
	realtimeError,
	realtimeState,
	validateEvent,
	type SocketLike,
} from "@/realtime";

/** A socket we drive by hand. */
function fakeSocket(): SocketLike & { emit: (event: string, payload?: unknown) => void } {
	const handlers = new Map<string, ((...args: unknown[]) => void)[]>();
	return {
		connected: false,
		on(event, handler) {
			handlers.set(event, [...(handlers.get(event) ?? []), handler]);
		},
		off() {},
		disconnect: vi.fn(),
		emit(event, payload) {
			for (const h of handlers.get(event) ?? []) h(payload);
		},
	};
}

beforeEach(() => _resetForTests());

describe("validateEvent", () => {
	it("accepts contract payloads and rejects anything else", () => {
		expect(
			validateEvent("infra:job.updated", { job: "JOB-1", status: "Running", progress: 40 })
				.ok
		).toBe(true);
		expect(
			validateEvent("infra:job.updated", { job: "JOB-1", status: "Bogus", progress: 40 }).ok
		).toBe(false);
		expect(
			validateEvent("infra:job.updated", {
				job: "JOB-1",
				status: "Running",
				progress: 40,
				extra: 1,
			}).ok
		).toBe(false);
		expect(
			validateEvent("infra:job.log", { job: "J", idx: 0, chunk: "x".repeat(4097) }).ok
		).toBe(false);
		expect(
			validateEvent("infra:server.heartbeat", {
				server: "SRV-1",
				status: "Active",
				cpu: 1,
				ram: 2,
				disk: 3,
				ts: "2026-10-07T09:30:00Z",
			}).ok
		).toBe(true);
	});
});

describe("socket", () => {
	it("connects to the site namespace, tracks state and dispatches validated events only", () => {
		const socket = fakeSocket();
		let seenNamespace = "";
		let seenPath = "";
		connectRealtime({
			site: "mock.localhost",
			factory: (ns, path) => {
				seenNamespace = ns;
				seenPath = path;
				return socket;
			},
		});
		expect(seenNamespace).toBe("/mock.localhost");
		expect(seenPath).toBe("/socket.io");
		expect(realtimeState.value).toBe("connecting");
		socket.emit("connect");
		expect(realtimeState.value).toBe("connected");

		const received: unknown[] = [];
		const off = onEvent("infra:job.updated", (p) => received.push(p));
		socket.emit("infra:job.updated", { job: "JOB-1", status: "Success", progress: 100 });
		socket.emit("infra:job.updated", { job: "JOB-1", status: "Nope", progress: 100 });
		expect(received).toEqual([{ job: "JOB-1", status: "Success", progress: 100 }]);
		expect(realtimeDropped.value).toBe(1);
		expect(realtimeError.value).toContain("infra:job.updated");

		off();
		socket.emit("infra:job.updated", { job: "JOB-2", status: "Queued", progress: 0 });
		expect(received).toHaveLength(1);

		socket.emit("connect_error", new Error("down"));
		expect(realtimeState.value).toBe("reconnecting");
		socket.emit("disconnect");
		expect(realtimeState.value).toBe("offline");
	});

	it("injectEvent feeds handlers through the same validation", () => {
		const got: string[] = [];
		onEvent("infra:inventory.changed", (e) => got.push(e.name));
		injectEvent("infra:inventory.changed", {
			doctype: "Site",
			name: "a.iq",
			change: "created",
		});
		injectEvent("infra:inventory.changed", {
			doctype: "Nope",
			name: "a.iq",
			change: "created",
		});
		expect(got).toEqual(["a.iq"]);
	});
});
