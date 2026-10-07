<script setup lang="ts">
import { X } from "lucide-vue-next";
import { transitions } from "@/design/motion";
import { toneClass } from "@/design/status";
import IcIconButton from "./IcIconButton.vue";
import { dismissToast, toasts } from "./useToasts";

const edge = {
	healthy: "border-s-healthy",
	degraded: "border-s-degraded",
	down: "border-s-down",
	running: "border-s-running",
	neutral: "border-s-neutral",
} as const;
</script>

<template>
	<Teleport to="body">
		<TransitionGroup
			tag="ol"
			:name="transitions.rise"
			class="fixed bottom-4 end-4 z-(--ic-z-toast) flex w-80 flex-col gap-2"
			aria-live="polite"
			data-testid="toast-host"
		>
			<li
				v-for="t in toasts.items"
				:key="t.id"
				class="flex items-start gap-3 rounded border border-line border-s-2 bg-surface-3 px-3 py-2.5 shadow-overlay"
				:class="edge[t.tone]"
				role="status"
			>
				<div class="flex min-w-0 flex-1 flex-col">
					<span class="font-medium" :class="toneClass[t.tone].text">{{ t.title }}</span>
					<span v-if="t.description" class="text-xs text-fg-muted">{{
						t.description
					}}</span>
				</div>
				<IcIconButton label="Dismiss" size="sm" @click="dismissToast(t.id)">
					<X :size="14" />
				</IcIconButton>
			</li>
		</TransitionGroup>
	</Teleport>
</template>
