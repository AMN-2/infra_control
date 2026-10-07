<script setup lang="ts">
import ShowcaseSection from "../ShowcaseSection.vue";
import TokenLabel from "../TokenLabel.vue";

const scale = [
	{ name: "--ic-text-3xl", cls: "text-3xl", px: 32, use: "Page titles" },
	{ name: "--ic-text-2xl", cls: "text-2xl", px: 24, use: "Section titles" },
	{ name: "--ic-text-xl", cls: "text-xl", px: 20, use: "Card titles" },
	{ name: "--ic-text-lg", cls: "text-lg", px: 16, use: "Emphasis" },
] as const;
const body = [
	{ name: "--ic-text-md", cls: "text-md", px: 14, use: "Comfortable body" },
	{ name: "--ic-text-sm", cls: "text-sm", px: 13, use: "Default UI text" },
	{ name: "--ic-text-xs", cls: "text-xs", px: 12, use: "Meta, table secondary" },
] as const;
</script>

<template>
	<ShowcaseSection
		id="type"
		title="Type"
		lead="Space Grotesk for headings and numerals, with tabular figures so live numbers don't jitter. System UI for body text (clear at 13px, and it falls back to a good Arabic face for RTL later). JetBrains Mono for anything an operator might copy: IPs, IDs, paths, logs."
	>
		<div class="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-6">
			<div class="flex flex-col gap-5 rounded border border-line bg-surface-1 p-6">
				<div class="flex items-end gap-6 border-b border-line pb-5">
					<span class="numerals text-4xl font-medium leading-none tracking-tight"
						>142</span
					>
					<span
						class="numerals text-4xl font-medium leading-none tracking-tight text-fg-muted"
					>
						98.7<span class="text-2xl">%</span>
					</span>
					<TokenLabel name="--ic-text-4xl · numerals" note="Hero numbers, tabular" />
				</div>
				<div v-for="s in scale" :key="s.name" class="flex items-baseline gap-4">
					<span class="w-12 shrink-0 numerals text-xs text-fg-subtle">{{ s.px }}</span>
					<span class="font-display font-semibold tracking-tight" :class="s.cls"
						>Server fleet</span
					>
					<span class="ms-auto text-xs text-fg-subtle">{{ s.use }}</span>
				</div>
			</div>

			<div class="flex flex-col gap-5 rounded border border-line bg-surface-1 p-6">
				<div v-for="s in body" :key="s.name" class="flex items-baseline gap-4">
					<span class="w-12 shrink-0 numerals text-xs text-fg-subtle">{{ s.px }}</span>
					<span :class="s.cls">Migrate 12 sites on erp-prod-02, canary first.</span>
				</div>
				<div class="flex items-baseline gap-4">
					<span class="w-12 shrink-0 numerals text-xs text-fg-subtle">11</span>
					<span class="eyebrow">Eyebrow label</span>
				</div>
				<div class="flex flex-col gap-2 border-t border-line pt-5 font-mono text-xs">
					<div class="flex gap-6">
						<span class="text-fg-subtle">ip</span><span>10.114.0.7</span>
						<span class="text-fg-subtle">job</span><span>JOB-2026-00042</span>
						<span class="text-fg-subtle">path</span
						><span>/home/frappe/frappe-bench</span>
					</div>
					<pre
						class="overflow-hidden rounded-sm bg-canvas p-3 leading-normal text-fg-muted"
					><span class="text-fg-subtle">12:04:11</span> TASK [bench : migrate site] ****
<span class="text-fg-subtle">12:04:13</span> <span class="text-healthy">ok</span>: [erp-prod-02] => acme.example.com
<span class="text-fg-subtle">12:04:13</span> <span class="text-degraded">changed</span>: [erp-prod-02] => patches applied: 14
<span class="text-fg-subtle">12:04:14</span> <span class="text-down">fatal</span>: [erp-prod-02] => ********** (masked)</pre>
				</div>
			</div>
		</div>
	</ShowcaseSection>
</template>
