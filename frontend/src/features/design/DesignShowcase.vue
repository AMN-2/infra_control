<script setup lang="ts">
import { ref } from "vue";
import { reducedMotion, setMotionOverride } from "@/design/motion";
import SurfacesSection from "./sections/SurfacesSection.vue";
import ColorSection from "./sections/ColorSection.vue";
import StatusSection from "./sections/StatusSection.vue";
import TypeSection from "./sections/TypeSection.vue";
import SpaceSection from "./sections/SpaceSection.vue";
import MotionSection from "./sections/MotionSection.vue";
import MomentsSection from "./sections/MomentsSection.vue";
import ComponentsSection from "./sections/ComponentsSection.vue";

const sections = [
	{ id: "moments", label: "Signature moments" },
	{ id: "surfaces", label: "Surfaces" },
	{ id: "color", label: "Colour" },
	{ id: "status", label: "Status" },
	{ id: "type", label: "Type" },
	{ id: "space", label: "Space & radius" },
	{ id: "motion", label: "Motion" },
	{ id: "components", label: "Components" },
] as const;

type Mode = "system" | "full" | "reduce";
const modes: { value: Mode; label: string }[] = [
	{ value: "system", label: "System" },
	{ value: "full", label: "Full" },
	{ value: "reduce", label: "Reduced" },
];
const mode = ref<Mode>("system");

function setMode(value: Mode): void {
	mode.value = value;
	setMotionOverride(value === "system" ? null : value);
}
</script>

<template>
	<div class="min-h-dvh">
		<header class="sticky top-0 z-(--ic-z-sticky) border-b border-line bg-canvas">
			<div class="mx-auto flex max-w-7xl items-center gap-6 px-6 py-3">
				<div class="flex items-baseline gap-3">
					<span class="font-display text-md font-semibold tracking-tight"
						>Infra Control</span
					>
					<span class="eyebrow">Design system · draft for review</span>
				</div>
				<div class="ms-auto flex items-center gap-3">
					<span id="motion-mode-label" class="eyebrow">Motion</span>
					<div
						class="flex rounded border border-line bg-surface-1 p-0.5"
						role="radiogroup"
						aria-labelledby="motion-mode-label"
						data-testid="motion-mode"
					>
						<button
							v-for="m in modes"
							:key="m.value"
							type="button"
							role="radio"
							:aria-checked="mode === m.value"
							class="ic-state-layer rounded-sm px-2.5 py-1 text-xs"
							:class="mode === m.value ? 'bg-surface-3 text-fg' : 'text-fg-muted'"
							@click="setMode(m.value)"
						>
							{{ m.label }}
						</button>
					</div>
					<span class="w-28 text-xs text-fg-subtle" aria-live="polite">
						{{ reducedMotion ? "reduced in effect" : "full motion" }}
					</span>
				</div>
			</div>
		</header>

		<div class="mx-auto grid max-w-7xl grid-cols-[11rem_minmax(0,1fr)] gap-10 px-6">
			<nav class="sticky top-16 self-start py-10" aria-label="Sections">
				<ul class="flex flex-col gap-1">
					<li v-for="s in sections" :key="s.id">
						<a
							:href="`#${s.id}`"
							class="ic-state-layer block rounded-sm px-2 py-1 text-fg-muted hover:text-fg"
						>
							{{ s.label }}
						</a>
					</li>
				</ul>
			</nav>

			<main class="flex flex-col gap-16 py-10" data-testid="design-showcase">
				<MomentsSection />
				<SurfacesSection />
				<ColorSection />
				<StatusSection />
				<TypeSection />
				<SpaceSection />
				<MotionSection />
				<ComponentsSection />
			</main>
		</div>
	</div>
</template>
