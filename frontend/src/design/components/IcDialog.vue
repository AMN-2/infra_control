<script setup lang="ts">
import { nextTick, onBeforeUnmount, useTemplateRef, watch } from "vue";
import { X } from "lucide-vue-next";
import { transitions } from "@/design/motion";
import IcIconButton from "./IcIconButton.vue";

const props = withDefaults(
	defineProps<{ title: string; description?: string; size?: "sm" | "md" | "lg" }>(),
	{ description: undefined, size: "md" }
);
const open = defineModel<boolean>({ default: false });
const emit = defineEmits<{ close: [] }>();

const panel = useTemplateRef<HTMLDivElement>("panel");
const sizeClass = { sm: "max-w-sm", md: "max-w-lg", lg: "max-w-3xl" } as const;

function close(): void {
	open.value = false;
	emit("close");
}
function onKey(e: KeyboardEvent): void {
	if (e.key === "Escape") close();
	if (e.key === "Tab" && panel.value) trapFocus(e, panel.value);
}
function trapFocus(e: KeyboardEvent, root: HTMLElement): void {
	const focusable = root.querySelectorAll<HTMLElement>(
		'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
	);
	const first = focusable[0];
	const last = focusable[focusable.length - 1];
	if (!first || !last) return;
	if (e.shiftKey && document.activeElement === first) {
		e.preventDefault();
		last.focus();
	} else if (!e.shiftKey && document.activeElement === last) {
		e.preventDefault();
		first.focus();
	}
}

let previous: Element | null = null;
watch(open, async (isOpen) => {
	if (isOpen) {
		previous = document.activeElement;
		document.addEventListener("keydown", onKey);
		await nextTick();
		const target = panel.value?.querySelector<HTMLElement>("[autofocus], input, button");
		(target ?? panel.value)?.focus();
	} else {
		document.removeEventListener("keydown", onKey);
		if (previous instanceof HTMLElement) previous.focus();
	}
});
onBeforeUnmount(() => {
	document.removeEventListener("keydown", onKey);
});
</script>

<template>
	<Teleport to="body">
		<Transition :name="transitions.fade">
			<div
				v-if="open"
				class="fixed inset-0 z-(--ic-z-overlay) grid place-items-center bg-scrim p-6"
				@click.self="close"
			>
				<Transition :name="transitions.scale" appear>
					<div
						ref="panel"
						role="dialog"
						aria-modal="true"
						:aria-labelledby="`dialog-title-${title}`"
						tabindex="-1"
						class="flex w-full flex-col rounded border border-line-strong bg-surface-3 shadow-overlay outline-none"
						:class="sizeClass[props.size]"
					>
						<header class="flex items-start gap-4 px-5 pt-5 pb-3">
							<div class="flex min-w-0 flex-col gap-1">
								<h2 :id="`dialog-title-${title}`" class="text-lg">{{ title }}</h2>
								<p v-if="description" class="text-fg-muted">{{ description }}</p>
							</div>
							<IcIconButton label="Close" size="sm" class="ms-auto" @click="close">
								<X :size="16" />
							</IcIconButton>
						</header>
						<div class="px-5 py-2">
							<slot />
						</div>
						<footer v-if="$slots.footer" class="flex justify-end gap-2 px-5 pt-3 pb-5">
							<slot name="footer" :close="close" />
						</footer>
					</div>
				</Transition>
			</div>
		</Transition>
	</Teleport>
</template>
