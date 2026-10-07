<script setup lang="ts">
import { computed } from "vue";
import { IcStatusDot, IcTooltip } from "@/design/components";
import { realtimeDropped, realtimeError, realtimeState } from "@/realtime";
import type { Tone } from "@/design/status";

const tone = computed<Tone>(() => {
	switch (realtimeState.value) {
		case "connected":
			return "healthy";
		case "connecting":
		case "reconnecting":
			return "running";
		case "offline":
			return "down";
		default:
			return "neutral";
	}
});
const label = computed(() => {
	const base = {
		idle: "Realtime idle",
		connecting: "Connecting",
		connected: "Live",
		reconnecting: "Reconnecting",
		offline: "Offline",
	}[realtimeState.value];
	return realtimeDropped.value
		? `${base} · ${realtimeDropped.value} invalid event(s) dropped`
		: base;
});
</script>

<template>
	<IcTooltip :text="realtimeError ?? label">
		<span
			class="flex items-center gap-2 text-xs text-fg-muted"
			data-testid="realtime-indicator"
			:data-state="realtimeState"
		>
			<IcStatusDot :tone="tone" :live="realtimeState === 'connected'" size="sm" />
			{{ label }}
		</span>
	</IcTooltip>
</template>
