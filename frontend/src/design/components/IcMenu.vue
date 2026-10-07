<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, useTemplateRef } from "vue";
import { transitions } from "@/design/motion";
import { toneClass, type Tone } from "@/design/status";
import IcKbd from "./IcKbd.vue";

export interface MenuItem {
	id: string;
	label: string;
	tone?: Tone;
	disabled?: boolean;
	kbd?: string;
	description?: string;
}
defineProps<{ items: readonly MenuItem[]; label: string }>();
const emit = defineEmits<{ select: [id: string] }>();

const open = ref(false);
const list = useTemplateRef<HTMLUListElement>("list");

function onDocumentClick(e: MouseEvent): void {
	if (!(e.target instanceof Node) || !list.value?.parentElement?.contains(e.target)) close();
}
async function toggle(): Promise<void> {
	open.value = !open.value;
	if (open.value) {
		document.addEventListener("click", onDocumentClick, true);
		await nextTick();
		list.value
			?.querySelector<HTMLElement>("[role=menuitem]:not([aria-disabled=true])")
			?.focus();
	} else close();
}
function close(): void {
	open.value = false;
	document.removeEventListener("click", onDocumentClick, true);
}
function choose(item: MenuItem): void {
	if (item.disabled) return;
	emit("select", item.id);
	close();
}
function focusSibling(delta: number): void {
	const items = [
		...(list.value?.querySelectorAll<HTMLElement>(
			"[role=menuitem]:not([aria-disabled=true])"
		) ?? []),
	];
	const i = items.indexOf(document.activeElement as HTMLElement);
	items[(i + delta + items.length) % items.length]?.focus();
}
onBeforeUnmount(close);
</script>

<template>
	<div class="relative inline-flex">
		<span @click="toggle" @keydown.arrow-down.prevent="toggle">
			<slot name="trigger" :open="open" />
		</span>
		<Transition :name="transitions.scale">
			<ul
				v-if="open"
				ref="list"
				role="menu"
				:aria-label="label"
				class="absolute end-0 top-full z-(--ic-z-popover) mt-1 flex min-w-48 origin-top-right flex-col rounded border border-line-strong bg-surface-3 p-1 shadow-overlay rtl:origin-top-left"
				@keydown.escape.prevent="close"
				@keydown.arrow-down.prevent="focusSibling(1)"
				@keydown.arrow-up.prevent="focusSibling(-1)"
			>
				<li v-for="item in items" :key="item.id">
					<button
						type="button"
						role="menuitem"
						:aria-disabled="item.disabled || undefined"
						class="ic-state-layer flex w-full items-center gap-3 rounded-sm px-2 py-1.5 text-start text-sm aria-disabled:cursor-not-allowed aria-disabled:opacity-50"
						:class="item.tone ? toneClass[item.tone].text : 'text-fg'"
						@click="choose(item)"
					>
						<span class="flex min-w-0 flex-col">
							<span class="truncate">{{ item.label }}</span>
							<span
								v-if="item.description"
								class="truncate text-xs text-fg-subtle"
								>{{ item.description }}</span
							>
						</span>
						<IcKbd v-if="item.kbd" class="ms-auto">{{ item.kbd }}</IcKbd>
					</button>
				</li>
			</ul>
		</Transition>
	</div>
</template>
