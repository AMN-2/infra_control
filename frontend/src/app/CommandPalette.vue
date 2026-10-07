<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, useTemplateRef, watch } from "vue";
import { useRouter } from "vue-router";
import { Search } from "lucide-vue-next";
import { play, presets, transitions } from "@/design/motion";
import { IcKbd, IcStatusBadge } from "@/design/components";
import { usePalette, type PaletteItem } from "./usePalette";

const router = useRouter();
const palette = usePalette(router);
const input = useTemplateRef<HTMLInputElement>("input");
const panel = useTemplateRef<HTMLDivElement>("panel");
const list = ref<HTMLElement | null>(null);

// Signature moment (Command palette): spring open, instant results.
watch(palette.open, async (isOpen) => {
	if (!isOpen) return;
	await nextTick();
	input.value?.focus();
	if (panel.value) play(panel.value, presets.scaleIn, { useSpring: true });
});
watch(palette.active, () => {
	list.value
		?.querySelector<HTMLElement>('[aria-selected="true"]')
		?.scrollIntoView({ block: "nearest" });
});

function groupOf(item: PaletteItem, index: number, items: readonly PaletteItem[]): string | null {
	return index === 0 || items[index - 1]?.group !== item.group ? item.group : null;
}
function statusEntity(item: PaletteItem): "server" | "site" | "job" | "alert" {
	if (item.group === "Servers") return "server";
	if (item.group === "Sites") return "site";
	if (item.group === "Jobs") return "job";
	return "alert";
}

onMounted(() => {
	document.addEventListener("keydown", palette.onKeydown);
});
onBeforeUnmount(() => {
	document.removeEventListener("keydown", palette.onKeydown);
});
defineExpose({ show: palette.show });
</script>

<template>
	<Teleport to="body">
		<Transition :name="transitions.fade">
			<div
				v-if="palette.open.value"
				class="fixed inset-0 z-(--ic-z-overlay) flex items-start justify-center bg-scrim p-6 pt-[12vh]"
				@click.self="palette.hide"
			>
				<div
					ref="panel"
					role="dialog"
					aria-modal="true"
					aria-label="Command palette"
					class="flex w-full max-w-xl flex-col overflow-hidden rounded border border-line-strong bg-surface-3 shadow-overlay"
					data-testid="command-palette"
				>
					<label class="flex items-center gap-3 border-b border-line px-4 py-3">
						<Search :size="16" class="shrink-0 text-fg-subtle" aria-hidden="true" />
						<input
							ref="input"
							:value="palette.query.value"
							type="search"
							placeholder="Go to a screen, or search servers, sites, jobs, playbooks…"
							class="min-w-0 flex-1 bg-transparent text-md text-fg outline-none placeholder:text-fg-subtle"
							role="combobox"
							aria-expanded="true"
							aria-controls="palette-results"
							:aria-activedescendant="
								palette.items.value[palette.active.value]
									? `palette-${palette.items.value[palette.active.value]?.id}`
									: undefined
							"
							autocomplete="off"
							@input="palette.setQuery(($event.target as HTMLInputElement).value)"
							@keydown.arrow-down.prevent="palette.move(1)"
							@keydown.arrow-up.prevent="palette.move(-1)"
							@keydown.enter.prevent="palette.choose()"
						/>
						<IcKbd>Esc</IcKbd>
					</label>
					<ul
						id="palette-results"
						ref="list"
						role="listbox"
						class="max-h-96 overflow-y-auto p-1.5"
					>
						<li
							v-if="palette.items.value.length === 0"
							class="px-3 py-6 text-center text-fg-subtle"
						>
							{{ palette.searching.value ? "Searching…" : "No matches" }}
						</li>
						<template v-for="(item, i) in palette.items.value" :key="item.id">
							<li
								v-if="groupOf(item, i, palette.items.value)"
								class="eyebrow px-2.5 pt-2 pb-1"
								role="presentation"
							>
								{{ item.group }}
							</li>
							<li
								:id="`palette-${item.id}`"
								role="option"
								:aria-selected="i === palette.active.value"
								class="flex cursor-pointer items-center gap-3 rounded-sm px-2.5 py-2"
								:class="
									i === palette.active.value
										? 'bg-surface-2 text-fg'
										: 'text-fg-muted'
								"
								@mousemove="palette.active.value = i"
								@click="palette.choose(item)"
							>
								<span class="flex min-w-0 flex-col">
									<span
										class="truncate"
										:class="{ 'font-mono text-sm': item.group !== 'Go to' }"
										>{{ item.title }}</span
									>
									<span
										v-if="item.subtitle"
										class="truncate text-xs text-fg-subtle"
										>{{ item.subtitle }}</span
									>
								</span>
								<span class="ms-auto flex shrink-0 items-center gap-2">
									<IcStatusBadge
										v-if="item.status"
										:entity="statusEntity(item)"
										:status="item.status"
									/>
									<IcKbd v-if="item.kbd">{{ item.kbd }}</IcKbd>
								</span>
							</li>
						</template>
					</ul>
				</div>
			</div>
		</Transition>
	</Teleport>
</template>
