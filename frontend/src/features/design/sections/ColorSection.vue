<script setup lang="ts">
import ShowcaseSection from "../ShowcaseSection.vue";
import TokenLabel from "../TokenLabel.vue";
import { useContrast } from "../useTokens";

const text = [
	{ name: "--ic-fg", cls: "text-fg", use: "Primary text, values" },
	{ name: "--ic-fg-muted", cls: "text-fg-muted", use: "Secondary text, labels" },
	{ name: "--ic-fg-subtle", cls: "text-fg-subtle", use: "Captions, eyebrows, timestamps" },
	{ name: "--ic-accent-text", cls: "text-accent-text", use: "Links, accent text" },
] as const;

const contrasts = text.map((t) => useContrast(t.name, "--ic-surface-1"));
const disabledContrast = useContrast("--ic-fg-disabled", "--ic-surface-1");
const buttonContrast = useContrast("--ic-accent-fg", "--ic-accent");
const hoverContrast = useContrast("--ic-accent-fg", "--ic-accent-hover");
</script>

<template>
	<ShowcaseSection
		id="color"
		title="Text & accent"
		lead="Four text levels, all WCAG AA on every surface (enforced by a unit test). One violet accent for actions only. It is hue-separated from running-blue so an action never reads as a state."
	>
		<div class="grid grid-cols-2 gap-6">
			<div class="rounded border border-line bg-surface-1">
				<div
					v-for="(t, i) in text"
					:key="t.name"
					class="flex items-center gap-4 border-b border-line px-5 py-4 last:border-b-0"
				>
					<span class="w-10 font-display text-2xl font-medium" :class="t.cls">Aa</span>
					<TokenLabel :name="t.name" :note="t.use" />
					<span class="ms-auto numerals text-xs text-fg-muted" data-testid="contrast">
						{{ contrasts[i]?.value }}
					</span>
				</div>
				<div class="flex items-center gap-4 px-5 py-4">
					<span class="w-10 font-display text-2xl font-medium text-fg-disabled">Aa</span>
					<TokenLabel
						name="--ic-fg-disabled"
						note="Disabled only. Not for information."
					/>
					<span class="ms-auto numerals text-xs text-fg-subtle">{{
						disabledContrast
					}}</span>
				</div>
			</div>

			<div class="flex flex-col gap-4 rounded border border-line bg-surface-1 p-5">
				<div class="flex gap-3">
					<div class="flex flex-1 flex-col gap-2">
						<span class="h-14 rounded-sm bg-accent" />
						<TokenLabel name="--ic-accent" />
					</div>
					<div class="flex flex-1 flex-col gap-2">
						<span class="h-14 rounded-sm bg-accent-hover" />
						<TokenLabel name="--ic-accent-hover" />
					</div>
					<div class="flex flex-1 flex-col gap-2">
						<span class="h-14 rounded-sm bg-accent-press" />
						<TokenLabel name="--ic-accent-press" />
					</div>
					<div class="flex flex-1 flex-col gap-2">
						<span class="h-14 rounded-sm border border-line bg-accent-soft" />
						<TokenLabel name="--ic-accent-soft" />
					</div>
				</div>
				<div class="mt-2 flex items-center gap-3 border-t border-line pt-4">
					<button
						type="button"
						class="accent-button ic-state-layer rounded bg-accent px-3.5 py-2 font-medium text-accent-fg"
					>
						Run playbook
					</button>
					<button
						type="button"
						class="ic-state-layer rounded border border-line-strong px-3.5 py-2 text-fg"
					>
						Cancel
					</button>
					<span class="ms-auto text-end text-xs text-fg-subtle">
						Label on accent {{ buttonContrast }} · on hover {{ hoverContrast }}
					</span>
				</div>
				<p class="text-xs text-fg-subtle">
					Hover and press only change opacity and transform (120 ms), never colour or
					layout. Focus uses a 2px accent ring; press <kbd>Tab</kbd> to see it.
				</p>
			</div>
		</div>
	</ShowcaseSection>
</template>

<style scoped>
.accent-button {
	--ic-state-color: var(--ic-accent-hover);
	--ic-state-hover-opacity: 1;
}
</style>
