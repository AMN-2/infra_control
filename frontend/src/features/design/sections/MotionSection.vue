<script setup lang="ts">
import { ref, useTemplateRef } from "vue";
import { animate } from "motion";
import ShowcaseSection from "../ShowcaseSection.vue";
import {
	duration,
	ease,
	play,
	presets,
	reducedMotion,
	spring,
	type Preset,
} from "@/design/motion";

const durations = [
	{ key: "press", token: "--ic-dur-press", use: "Hover, press: feedback" },
	{ key: "base", token: "--ic-dur-base", use: "Most transitions: fades, rows, tabs" },
	{ key: "emphasis", token: "--ic-dur-emphasis", use: "Dialogs, panels, shared elements" },
	{ key: "scene", token: "--ic-dur-scene", use: "Large scenes. The hard maximum." },
] as const;

const markers = useTemplateRef<HTMLElement[]>("marker");
const tracks = useTemplateRef<HTMLElement[]>("track");
let forward = true;

function runDurations(): void {
	durations.forEach((d, i) => {
		const marker = markers.value?.[i];
		const track = tracks.value?.[i];
		if (!marker || !track) return;
		const travel = track.clientWidth - marker.offsetWidth;
		const to = `translateX(${forward ? travel : 0}px)`;
		if (reducedMotion.value) {
			marker.style.transform = to;
			return;
		}
		animate(marker, { transform: to }, { duration: duration[d.key], ease });
	});
	forward = !forward;
}

// Easing curve plotted in a 100×100 box (y grows downwards in SVG).
const [x1, y1, x2, y2] = ease;
const curve = `M0,100 C${x1 * 100},${100 - y1 * 100} ${x2 * 100},${100 - y2 * 100} 100,0`;

const panelOpen = ref(false);
function onPanelEnter(el: Element, done: () => void): void {
	const controls = play(el, presets.scaleIn, { useSpring: true });
	if (controls) void controls.finished.then(done);
	else done();
}
function onPanelLeave(el: Element, done: () => void): void {
	if (reducedMotion.value) {
		done();
		return;
	}
	void animate(
		el,
		{ opacity: 0, transform: "scale(0.98)" },
		{ duration: duration.press, ease }
	).finished.then(done);
}

const presetTiles: { name: string; preset: Preset; use: string }[] = [
	{ name: "fadeIn", preset: presets.fadeIn, use: "Content swaps in place" },
	{ name: "riseIn", preset: presets.riseIn, use: "New row, alert, card" },
	{ name: "scaleIn", preset: presets.scaleIn, use: "Overlays opening" },
];
const tiles = useTemplateRef<HTMLElement[]>("tile");
function replay(i: number): void {
	const el = tiles.value?.[i];
	const tile = presetTiles[i];
	if (el && tile) play(el, tile.preset);
}
</script>

<template>
	<ShowcaseSection
		id="motion"
		title="Motion"
		lead="Motion explains state; it never decorates. One easing, one spring, four durations, transform and opacity only. Under reduced motion every duration drops to zero and only essential opacity fades remain. Use the switch in the header to compare."
	>
		<div class="grid grid-cols-[minmax(0,2fr)_minmax(0,1fr)] gap-6">
			<div class="rounded border border-line bg-surface-1 p-6">
				<div class="mb-4 flex items-center justify-between">
					<h3 class="text-md">Durations</h3>
					<button
						type="button"
						class="ic-state-layer rounded border border-line-strong px-3 py-1.5 text-xs"
						data-testid="play-durations"
						@click="runDurations"
					>
						Play
					</button>
				</div>
				<div class="flex flex-col gap-4">
					<div
						v-for="d in durations"
						:key="d.key"
						class="grid grid-cols-[13rem_minmax(0,1fr)] items-center gap-4"
					>
						<div class="flex flex-col">
							<span class="numerals text-md">{{ duration[d.key] * 1000 }} ms</span>
							<span class="text-xs text-fg-subtle">{{ d.use }}</span>
						</div>
						<div ref="track" class="relative h-6 rounded-full bg-canvas" dir="ltr">
							<span
								ref="marker"
								class="absolute inset-y-1 start-1 w-4 rounded-full bg-accent"
							/>
						</div>
					</div>
				</div>
			</div>

			<div class="flex flex-col gap-3 rounded border border-line bg-surface-1 p-6">
				<h3 class="text-md">Easing</h3>
				<svg
					viewBox="-4 -4 108 108"
					class="aspect-square w-full"
					aria-label="Easing curve"
				>
					<path
						d="M0,100 L100,0"
						class="stroke-line-strong"
						fill="none"
						stroke-dasharray="2 3"
						vector-effect="non-scaling-stroke"
					/>
					<path
						d="M0,0 H100 V100 H0 Z"
						class="stroke-line"
						fill="none"
						vector-effect="non-scaling-stroke"
					/>
					<path
						:d="curve"
						class="stroke-accent-text"
						fill="none"
						stroke-width="2"
						vector-effect="non-scaling-stroke"
					/>
				</svg>
				<code class="text-xs">--ic-ease · bezier [{{ ease.join(", ") }}]</code>
				<p class="text-xs text-fg-subtle">
					Fast response, long gentle settle. Used for every enter and exit, so the whole
					UI moves with one voice.
				</p>
			</div>
		</div>

		<div class="mt-6 grid grid-cols-[minmax(0,1fr)_minmax(0,2fr)] gap-6">
			<div class="flex flex-col gap-4 rounded border border-line bg-surface-1 p-6">
				<div class="flex items-center justify-between">
					<h3 class="text-md">Spring</h3>
					<button
						type="button"
						class="ic-state-layer rounded border border-line-strong px-3 py-1.5 text-xs"
						data-testid="toggle-spring"
						@click="panelOpen = !panelOpen"
					>
						{{ panelOpen ? "Close" : "Open" }}
					</button>
				</div>
				<div class="grid h-32 place-items-center rounded-sm bg-canvas">
					<Transition :css="false" @enter="onPanelEnter" @leave="onPanelLeave">
						<div
							v-if="panelOpen"
							class="w-4/5 rounded border border-line-strong bg-surface-3 p-4 shadow-overlay"
						>
							<span class="text-xs text-fg-muted">Command palette, dialogs</span>
						</div>
						<span v-else class="text-xs text-fg-subtle">Press Open</span>
					</Transition>
				</div>
				<code class="text-xs">
					spring · visualDuration {{ spring.visualDuration }}s · bounce
					{{ spring.bounce }}
				</code>
			</div>

			<div class="flex flex-col gap-4 rounded border border-line bg-surface-1 p-6">
				<h3 class="text-md">Presets <span class="eyebrow ms-2">click to replay</span></h3>
				<div class="grid grid-cols-3 gap-3">
					<button
						v-for="(t, i) in presetTiles"
						:key="t.name"
						type="button"
						class="ic-state-layer flex h-32 flex-col items-start justify-end gap-1 rounded-sm bg-canvas p-3 text-start"
						@click="replay(i)"
					>
						<span
							ref="tile"
							class="mb-auto h-10 w-full rounded-sm border border-line-strong bg-surface-2"
						/>
						<code class="text-xs text-fg">{{ t.name }}</code>
						<span class="text-xs text-fg-subtle">{{ t.use }}</span>
					</button>
				</div>
				<p class="text-xs text-fg-subtle">
					Under reduced motion, presets fall back to a {{ duration.press * 1000 }} ms
					opacity fade; press feedback and travel are removed entirely.
				</p>
			</div>
		</div>
	</ShowcaseSection>
</template>
