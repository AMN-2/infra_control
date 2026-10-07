<script setup lang="ts">
import { onBeforeUnmount, onMounted, useTemplateRef } from "vue";
import type { Terminal } from "@xterm/xterm";
import { token } from "@/design/tokens";
import { createLogBuffer } from "./logBuffer";

/**
 * Live log viewer (plan §2: xterm.js). xterm is loaded lazily so it never enters the initial
 * bundle. Parents push chunks through the exposed `write()`; chunks are buffered and flushed
 * at most every 50 ms (§10.4).
 */
const props = withDefaults(defineProps<{ rows?: number; initial?: string }>(), {
	rows: 18,
	initial: "",
});

const host = useTemplateRef<HTMLDivElement>("host");
let term: Terminal | null = null;
let pending = "";
const buffer = createLogBuffer((text) => {
	if (term) term.write(text.replaceAll(/(?<!\r)\n/g, "\r\n"));
	else pending += text;
});
let resizeObserver: ResizeObserver | null = null;

onMounted(async () => {
	const [{ Terminal: XTerm }, { FitAddon }] = await Promise.all([
		import("@xterm/xterm"),
		import("@xterm/addon-fit"),
		import("@xterm/xterm/css/xterm.css"),
	]);
	if (!host.value) return;
	term = new XTerm({
		rows: props.rows,
		convertEol: false,
		disableStdin: true,
		cursorBlink: false,
		fontFamily: token("--ic-font-mono"),
		fontSize: 12,
		lineHeight: 1.4,
		theme: {
			background: token("--ic-canvas"),
			foreground: token("--ic-fg-muted"),
			selectionBackground: token("--ic-accent-soft"),
		},
	});
	const fit = new FitAddon();
	term.loadAddon(fit);
	term.open(host.value);
	fit.fit();
	resizeObserver = new ResizeObserver(() => {
		fit.fit();
	});
	resizeObserver.observe(host.value);
	if (props.initial) buffer.push(props.initial);
	if (pending) {
		term.write(pending.replaceAll(/(?<!\r)\n/g, "\r\n"));
		pending = "";
	}
	buffer.flushNow();
});
onBeforeUnmount(() => {
	resizeObserver?.disconnect();
	term?.dispose();
});

defineExpose({
	write: (chunk: string) => {
		buffer.push(chunk);
	},
	clear: () => term?.clear(),
});
</script>

<template>
	<div
		ref="host"
		class="min-h-40 overflow-hidden rounded border border-line bg-canvas p-2"
		data-testid="terminal"
		role="log"
		aria-live="polite"
	/>
</template>
