<script setup lang="ts">
import ShowcaseSection from "../ShowcaseSection.vue";
import TokenLabel from "../TokenLabel.vue";

/** Steps of the 4px grid in use. The class strings are literal so Tailwind can see them. */
const steps = [
	{ n: 1, cls: "w-1" },
	{ n: 2, cls: "w-2" },
	{ n: 3, cls: "w-3" },
	{ n: 4, cls: "w-4" },
	{ n: 6, cls: "w-6" },
	{ n: 8, cls: "w-8" },
	{ n: 10, cls: "w-10" },
	{ n: 12, cls: "w-12" },
	{ n: 16, cls: "w-16" },
] as const;
</script>

<template>
	<ShowcaseSection
		id="space"
		title="Space & radius"
		lead="Everything sits on a 4px grid (--ic-space-unit); Tailwind's spacing scale is mapped to it. Radius is 8px for containers, 4px for things inside them, and full for dots and pills."
	>
		<div class="grid grid-cols-[minmax(0,2fr)_minmax(0,1fr)] gap-6">
			<div class="flex flex-col gap-2 rounded border border-line bg-surface-1 p-6">
				<div v-for="s in steps" :key="s.n" class="flex items-center gap-4">
					<span class="w-16 numerals text-xs text-fg-subtle">{{ s.n * 4 }}px</span>
					<span class="h-3 rounded-sm bg-accent-soft" :class="s.cls" />
					<code class="text-xs text-fg-subtle">{{ s.n }}</code>
				</div>
			</div>
			<div class="flex flex-col gap-4 rounded border border-line bg-surface-1 p-6">
				<div class="flex items-center gap-4">
					<span class="size-12 rounded border border-line-strong bg-surface-2" />
					<TokenLabel name="--ic-radius" note="8px: cards, dialogs, buttons" />
				</div>
				<div class="flex items-center gap-4">
					<span class="size-12 rounded-sm border border-line-strong bg-surface-2" />
					<TokenLabel name="--ic-radius-sm" note="4px: nested, chips, inputs" />
				</div>
				<div class="flex items-center gap-4">
					<span class="size-12 rounded-full border border-line-strong bg-surface-2" />
					<TokenLabel name="--ic-radius-full" note="Dots, pills, avatars" />
				</div>
			</div>
		</div>
	</ShowcaseSection>
</template>
