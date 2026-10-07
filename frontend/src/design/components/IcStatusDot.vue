<script setup lang="ts">
import { toneClass, type Tone } from "@/design/status";

withDefaults(defineProps<{ tone: Tone; live?: boolean; size?: "sm" | "md" }>(), {
	live: false,
	size: "md",
});
</script>

<template>
	<span
		class="inline-block shrink-0 rounded-full"
		:class="[
			toneClass[tone].bg,
			toneClass[tone].text,
			size === 'sm' ? 'size-1.5' : 'size-2',
			{ 'ic-pulse': live },
		]"
		aria-hidden="true"
	/>
</template>
