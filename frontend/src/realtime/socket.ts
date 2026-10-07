/**
 * The only module that touches Socket.IO (plan §10.4). Mirrors Frappe's transport
 * (contracts/README.md): namespace `/<site>`, path `/socket.io`, cookie auth, no room join.
 * Every incoming payload is validated against contracts/events before any store sees it.
 */
import { io, type Socket } from "socket.io-client";
import { readonly, ref } from "vue";
import type { EventMap, EventName } from "./events.generated";
import { eventNames, validateEvent } from "./validate";

export type ConnectionState = "idle" | "connecting" | "connected" | "reconnecting" | "offline";
export type Handler<E extends EventName> = (payload: EventMap[E]) => void;

/** The subset of a Socket.IO client we use; tests inject a fake. */
export interface SocketLike {
	on: (event: string, handler: (...args: unknown[]) => void) => unknown;
	off: (event: string, handler?: (...args: unknown[]) => void) => unknown;
	disconnect: () => unknown;
	connected: boolean;
}
export type SocketFactory = (namespace: string, path: string) => SocketLike;

const defaultFactory: SocketFactory = (namespace, path) =>
	io(namespace, {
		path,
		withCredentials: true,
		transports: ["websocket", "polling"],
	});

const state = ref<ConnectionState>("idle");
const lastError = ref<string | null>(null);
const dropped = ref(0);

const handlers = new Map<EventName, Set<Handler<EventName>>>();
let socket: SocketLike | null = null;
let listening: Socket | SocketLike | null = null;

function dispatch(event: EventName, raw: unknown): void {
	const result = validateEvent(event, raw);
	if (!result.ok) {
		dropped.value += 1;
		lastError.value = `${event}: ${result.error}`;
		return;
	}
	for (const h of handlers.get(event) ?? []) h(result.payload);
}

/** Connect once per site. Safe to call again; it is a no-op while connected. */
export function connectRealtime(
	options: { site: string; origin?: string; factory?: SocketFactory; path?: string } = {
		site: "",
	}
): void {
	if (socket) return;
	const factory = options.factory ?? defaultFactory;
	const namespace = `${options.origin ?? ""}/${options.site}`;
	state.value = "connecting";
	socket = factory(namespace, options.path ?? "/socket.io");
	listening = socket;
	socket.on("connect", () => {
		state.value = "connected";
		lastError.value = null;
	});
	socket.on("disconnect", () => {
		state.value = "offline";
	});
	socket.on("connect_error", (err: unknown) => {
		state.value = "reconnecting";
		lastError.value = err instanceof Error ? err.message : String(err);
	});
	for (const event of eventNames) {
		socket.on(event, (payload: unknown) => {
			dispatch(event, payload);
		});
	}
}

export function disconnectRealtime(): void {
	listening?.disconnect();
	socket = null;
	listening = null;
	state.value = "idle";
}

/** Typed subscription. Returns the unsubscribe function. */
export function onEvent<E extends EventName>(event: E, handler: Handler<E>): () => void {
	let set = handlers.get(event);
	if (!set) {
		set = new Set();
		handlers.set(event, set);
	}
	set.add(handler as Handler<EventName>);
	return () => {
		set.delete(handler as Handler<EventName>);
	};
}

/** Test seam and mock replay hook: feed an event as if it came from the socket. */
export function injectEvent(event: EventName, payload: unknown): void {
	dispatch(event, payload);
}

export const realtimeState = readonly(state);
export const realtimeError = readonly(lastError);
export const realtimeDropped = readonly(dropped);

export function _resetForTests(): void {
	disconnectRealtime();
	handlers.clear();
	dropped.value = 0;
	lastError.value = null;
}
