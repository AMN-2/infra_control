<script setup lang="ts">
import ShowcaseSection from "../ShowcaseSection.vue";
import {
	alertSeverityTone,
	jobStatusTone,
	liveStates,
	serverStatusTone,
	siteStatusTone,
	toneLabel,
	type Tone,
} from "@/design/status";
import { useContrast } from "../useTokens";

const tones: { tone: Tone; meaning: string }[] = [
	{ tone: "healthy", meaning: "Working as intended" },
	{ tone: "degraded", meaning: "Working, needs attention" },
	{ tone: "down", meaning: "Not working, or failed" },
	{ tone: "running", meaning: "In motion: a job, provisioning, waiting in queue" },
	{ tone: "neutral", meaning: "Deliberately inactive: archived, suspended, skipped" },
];

/** Tailwind needs literal class names, so map tone → classes here rather than interpolating. */
const toneClass: Record<Tone, { text: string; soft: string; dot: string }> = {
	healthy: { text: "text-healthy", soft: "bg-healthy-soft", dot: "bg-healthy" },
	degraded: { text: "text-degraded", soft: "bg-degraded-soft", dot: "bg-degraded" },
	down: { text: "text-down", soft: "bg-down-soft", dot: "bg-down" },
	running: { text: "text-running", soft: "bg-running-soft", dot: "bg-running" },
	neutral: { text: "text-neutral", soft: "bg-neutral-soft", dot: "bg-neutral" },
};

const contrast = Object.fromEntries(
	tones.map(({ tone }) => [tone, useContrast(`--ic-${tone}`, "--ic-surface-1")])
);

const groups: { entity: string; map: Record<string, Tone> }[] = [
	{ entity: "Server", map: serverStatusTone },
	{ entity: "Site", map: siteStatusTone },
	{ entity: "Job / step", map: jobStatusTone },
	{ entity: "Alert severity", map: alertSeverityTone },
];
</script>

<template>
	<ShowcaseSection
		id="status"
		title="Status"
		lead="Five tones, identical on every screen. Only states that are genuinely moving (Running, Provisioning) pulse; waiting states stay still. Colour is never the only signal: every status also carries a label."
	>
		<div class="grid grid-cols-5 gap-3">
			<div
				v-for="t in tones"
				:key="t.tone"
				class="flex flex-col gap-3 rounded border border-line bg-surface-1 p-4"
				:data-testid="`tone-${t.tone}`"
			>
				<div class="flex items-center gap-2.5">
					<span
						class="size-2 rounded-full"
						:class="[
							toneClass[t.tone].dot,
							toneClass[t.tone].text,
							{ 'ic-pulse': t.tone === 'running' },
						]"
					/>
					<span class="font-medium" :class="toneClass[t.tone].text">{{
						toneLabel[t.tone]
					}}</span>
				</div>
				<span
					class="self-start rounded-full px-2 py-0.5 text-xs font-medium"
					:class="[toneClass[t.tone].soft, toneClass[t.tone].text]"
				>
					{{ toneLabel[t.tone] }}
				</span>
				<p class="text-xs text-fg-muted">{{ t.meaning }}</p>
				<code class="mt-auto text-2xs text-fg-subtle"
					>--ic-{{ t.tone }} · {{ contrast[t.tone]?.value }}</code
				>
			</div>
		</div>

		<h3 class="mt-8 mb-3 text-md">
			State mapping <span class="eyebrow ms-2">for review: Q-B5</span>
		</h3>
		<div class="overflow-hidden rounded border border-line bg-surface-1">
			<div
				v-for="g in groups"
				:key="g.entity"
				class="flex items-center gap-4 border-b border-line px-5 py-3 last:border-b-0"
			>
				<span class="w-32 shrink-0 text-fg-muted">{{ g.entity }}</span>
				<div class="flex flex-wrap gap-2">
					<span
						v-for="(tone, state) in g.map"
						:key="state"
						class="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs"
						:class="[toneClass[tone].soft, toneClass[tone].text]"
					>
						<span
							class="size-1.5 rounded-full"
							:class="[toneClass[tone].dot, { 'ic-pulse': liveStates.has(state) }]"
						/>
						{{ state }}
					</span>
				</div>
			</div>
		</div>
	</ShowcaseSection>
</template>
