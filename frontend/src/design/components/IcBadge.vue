<script setup lang="ts">
import { toneClass, type Tone } from "@/design/status";
import IcStatusDot from "./IcStatusDot.vue";

withDefaults(
	defineProps<{
		tone?: Tone;
		dot?: boolean;
		live?: boolean;
		mono?: boolean;
		uppercase?: boolean;
	}>(),
	{ tone: "neutral", dot: false, live: false, mono: false, uppercase: false }
);
</script>

<template>
	<span
		class="inline-flex shrink-0 items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap"
		:class="[
			toneClass[tone].soft,
			toneClass[tone].text,
			{ 'font-mono': mono, 'text-2xs uppercase tracking-wide': uppercase },
		]"
	>
		<IcStatusDot v-if="dot" :tone="tone" :live="live" size="sm" />
		<slot />
	</span>
</template>
