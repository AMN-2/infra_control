<script setup lang="ts">
import { computed, onBeforeUnmount, ref, useTemplateRef } from "vue";
import type { Terminal } from "@xterm/xterm";
import { IcBadge, IcButton } from "@/design/components";
import { reducedMotion } from "@/design/motion";
import { token } from "@/design/tokens";
import { useConsoleStore } from "@/stores/console";

/**
 * Interactive SSH terminal (ADR 0007). Open → `console.ticket` → WebSocket to `/console/ws`
 * on this origin → bytes both ways; resizes go as JSON control frames. The session is
 * recorded on the controller; the status line says so and names the session id.
 */
const props = defineProps<{ server: string; hostname: string }>();
const emit = defineEmits<{ closed: [session: string | null] }>();
const consoleStore = useConsoleStore();

type State = "idle" | "connecting" | "open" | "closed" | "failed";
const state = ref<State>("idle");
const session = ref<string | null>(null);
const detail = ref("");
const host = useTemplateRef<HTMLDivElement>("host");
let term: Terminal | null = null;
let ws: WebSocket | null = null;
let fitAddon: { fit: () => void } | null = null;
let resizeObserver: ResizeObserver | null = null;
let startedAt = 0;

const stateTone = computed(
	() =>
		(
			({
				idle: "neutral",
				connecting: "running",
				open: "healthy",
				closed: "neutral",
				failed: "down",
			}) as const
		)[state.value]
);

async function ensureTerminal(): Promise<Terminal> {
	if (term) return term;
	const [{ Terminal: XTerm }, { FitAddon }] = await Promise.all([
		import("@xterm/xterm"),
		import("@xterm/addon-fit"),
		import("@xterm/xterm/css/xterm.css"),
	]);
	term = new XTerm({
		rows: 24,
		cursorBlink: !reducedMotion.value,
		fontFamily: token("--ic-font-mono"),
		fontSize: 13,
		lineHeight: 1.3,
		theme: {
			background: token("--ic-canvas"),
			foreground: token("--ic-fg"),
			cursor: token("--ic-accent"),
			selectionBackground: token("--ic-accent-soft"),
		},
	});
	const fit = new FitAddon();
	fitAddon = fit;
	term.loadAddon(fit);
	if (host.value) term.open(host.value);
	fit.fit();
	term.onData((data) => {
		if (ws?.readyState === WebSocket.OPEN) ws.send(new TextEncoder().encode(data));
	});
	term.onResize(({ cols, rows }) => {
		if (ws?.readyState === WebSocket.OPEN)
			ws.send(JSON.stringify({ t: "resize", cols, rows }));
	});
	if (host.value) {
		resizeObserver = new ResizeObserver(() => fitAddon?.fit());
		resizeObserver.observe(host.value);
	}
	return term;
}

async function open(): Promise<void> {
	if (state.value === "connecting" || state.value === "open") return;
	state.value = "connecting";
	detail.value = "requesting a certificate…";
	const t = await ensureTerminal();
	t.clear();
	const ticket = await consoleStore.ticket(props.server);
	if (!ticket) {
		state.value = "failed";
		detail.value = consoleStore.error
			? `${consoleStore.error.message} (${consoleStore.error.code})`
			: "no ticket";
		return;
	}
	session.value = ticket.session;
	const scheme = location.protocol === "https:" ? "wss" : "ws";
	const url = `${scheme}://${location.host}${ticket.path}?ticket=${encodeURIComponent(ticket.ticket)}`;
	detail.value = `connecting as ${ticket.user}@${ticket.hostname}…`;
	const socket = new WebSocket(url);
	socket.binaryType = "arraybuffer";
	ws = socket;
	// A bridge that never answers the upgrade must not leave the operator "connecting" forever.
	const connectTimer = setTimeout(() => {
		if (state.value === "connecting") {
			state.value = "failed";
			detail.value = "the console service did not answer within 10 s";
			socket.close();
		}
	}, 10_000);
	socket.onopen = () => {
		clearTimeout(connectTimer);
		state.value = "open";
		startedAt = Date.now();
		detail.value = `session ${ticket.session} is being recorded`;
		socket.send(JSON.stringify({ t: "resize", cols: t.cols, rows: t.rows }));
		t.focus();
	};
	socket.onmessage = (e) => {
		if (e.data instanceof ArrayBuffer) t.write(new Uint8Array(e.data));
		else if (typeof e.data === "string") t.write(e.data);
	};
	socket.onerror = () => {
		if (state.value !== "open") {
			state.value = "failed";
			detail.value =
				"the console service did not answer (is the console component running?)";
		}
	};
	socket.onclose = (e) => {
		clearTimeout(connectTimer);
		if (state.value === "open") {
			const mins = Math.round((Date.now() - startedAt) / 60000);
			detail.value = `closed after ${mins} min · transcript ${ticket.session}`;
			state.value = "closed";
		} else if (state.value !== "failed") {
			state.value = "failed";
			detail.value = e.reason || "connection refused";
		}
		ws = null;
		emit("closed", ticket.session);
	};
}
function close(): void {
	ws?.close();
}
onBeforeUnmount(() => {
	ws?.close();
	resizeObserver?.disconnect();
	term?.dispose();
});
</script>

<template>
	<div class="flex flex-col gap-3" data-testid="ssh-terminal">
		<div class="flex flex-wrap items-center gap-2 text-xs text-fg-subtle">
			<IcButton
				v-if="state !== 'open' && state !== 'connecting'"
				variant="primary"
				size="sm"
				data-testid="ssh-open"
				@click="open"
				>Open terminal</IcButton
			>
			<IcButton
				v-else
				size="sm"
				variant="danger"
				:disabled="state === 'connecting'"
				data-testid="ssh-close"
				@click="close"
				>Disconnect</IcButton
			>
			<IcBadge :tone="stateTone" dot :live="state === 'open'" uppercase>{{ state }}</IcBadge>
			<span class="font-mono text-fg-muted">frappe@{{ hostname }}</span>
			<span data-testid="ssh-detail">{{ detail }}</span>
		</div>
		<div
			ref="host"
			class="min-h-72 overflow-hidden rounded border border-line bg-canvas p-2"
			:class="{ 'opacity-60': state !== 'open' }"
			data-testid="ssh-xterm"
		/>
		<p class="text-2xs text-fg-subtle">
			A fresh certificate valid for 10 minutes opens the session; the session itself lasts
			until you disconnect, 30 minutes idle, or 4 hours. Everything shown here is recorded
			under Sessions.
		</p>
	</div>
</template>
