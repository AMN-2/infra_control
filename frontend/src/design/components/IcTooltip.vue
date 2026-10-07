<script setup lang="ts">
import { ref } from "vue";
import { transitions } from "@/design/motion";

defineProps<{ text: string }>();
const shown = ref(false);
</script>

<template>
	<span
		class="relative inline-flex"
		@mouseenter="shown = true"
		@mouseleave="shown = false"
		@focusin="shown = true"
		@focusout="shown = false"
	>
		<slot />
		<Transition :name="transitions.fade">
			<span
				v-if="shown"
				role="tooltip"
				class="pointer-events-none absolute start-1/2 bottom-full z-(--ic-z-popover) mb-1.5 -translate-x-1/2 rounded-sm border border-line-strong bg-surface-3 px-2 py-1 text-xs whitespace-nowrap text-fg shadow-overlay rtl:translate-x-1/2"
			>
				{{ text }}
			</span>
		</Transition>
	</span>
</template>
