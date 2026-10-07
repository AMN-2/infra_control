<script setup lang="ts">
import ShowcaseSection from "../ShowcaseSection.vue";
import TokenLabel from "../TokenLabel.vue";
</script>

<template>
	<ShowcaseSection
		id="surfaces"
		title="Surfaces & edges"
		lead="Near-black with a slight blue tint. Elevation comes from lightness, not shadow: canvas, then three levels. Edges are 1px translucent lines, so they adapt to whatever surface they sit on."
	>
		<div class="rounded border border-line bg-canvas p-6" data-testid="surface-stack">
			<TokenLabel name="--ic-canvas" note="Page background" />
			<div class="mt-4 rounded border border-line bg-surface-1 p-6">
				<TokenLabel name="--ic-surface-1" note="Panels, cards, tables" />
				<div class="mt-4 rounded border border-line bg-surface-2 p-6">
					<TokenLabel
						name="--ic-surface-2"
						note="Raised: hover rows, inputs, popovers"
					/>
					<div
						class="mt-4 rounded border border-line-strong bg-surface-3 p-6 shadow-overlay"
					>
						<TokenLabel
							name="--ic-surface-3"
							note="Overlays: dialogs, command palette, toasts. The only level with a shadow."
						/>
					</div>
				</div>
			</div>
		</div>

		<div class="mt-6 grid grid-cols-2 gap-4">
			<div class="flex items-center gap-4 rounded border border-line bg-surface-1 p-4">
				<span class="h-10 w-16 rounded-sm border border-line" />
				<TokenLabel name="--ic-line" note="Default 1px edge" />
			</div>
			<div class="flex items-center gap-4 rounded border border-line bg-surface-1 p-4">
				<span class="h-10 w-16 rounded-sm border border-line-strong" />
				<TokenLabel name="--ic-line-strong" note="Overlays, focused containers" />
			</div>
		</div>
	</ShowcaseSection>
</template>
