<script setup lang="ts">
import { useTemplateRef } from "vue";
import { RouterLink, RouterView, useRoute } from "vue-router";
import { Command, Github, Palette, ScrollText, ShieldCheck } from "lucide-vue-next";
import { IcIconButton, IcKbd } from "@/design/components";
import { transitions } from "@/design/motion";
import { useSessionStore } from "@/stores/session";
import CommandPalette from "./CommandPalette.vue";
import RealtimeIndicator from "./RealtimeIndicator.vue";
import { navigation } from "./navigation";

const session = useSessionStore();
const route = useRoute();
const palette = useTemplateRef<InstanceType<typeof CommandPalette>>("palette");

function isActive(to: string): boolean {
	return route.path === to || route.path.startsWith(`${to}/`);
}
</script>

<template>
	<div class="grid min-h-dvh grid-cols-[14rem_minmax(0,1fr)]" data-testid="app-shell">
		<aside class="sticky top-0 flex h-dvh flex-col border-e border-line bg-surface-1">
			<RouterLink to="/overview" class="flex items-center gap-2 px-5 py-4">
				<span class="font-display text-md font-semibold tracking-tight"
					>Infra Control</span
				>
				<span class="eyebrow">beta</span>
			</RouterLink>
			<nav aria-label="Primary" class="flex flex-col gap-0.5 px-3">
				<RouterLink
					v-for="item in navigation"
					:key="item.name"
					:to="item.to"
					class="ic-state-layer flex items-center gap-3 rounded-sm px-2 py-1.5 text-sm"
					:class="
						isActive(item.to) ? 'bg-surface-3 text-fg' : 'text-fg-muted hover:text-fg'
					"
					:aria-current="isActive(item.to) ? 'page' : undefined"
					:data-testid="`nav-${item.name}`"
				>
					<component :is="item.icon" :size="16" aria-hidden="true" />
					{{ item.label }}
				</RouterLink>
			</nav>
			<div
				class="mt-auto flex flex-col gap-3 border-t border-line px-5 py-4 text-xs text-fg-subtle"
			>
				<RouterLink
					to="/audit"
					class="flex items-center gap-2 hover:text-fg"
					data-testid="nav-audit"
				>
					<ScrollText :size="14" aria-hidden="true" /> Audit log
				</RouterLink>
				<RouterLink
					v-if="session.isAdmin"
					to="/settings/security"
					class="flex items-center gap-2 hover:text-fg"
					data-testid="nav-security"
				>
					<ShieldCheck :size="14" aria-hidden="true" /> Security
				</RouterLink>
				<RouterLink
					v-if="session.isAdmin"
					to="/settings/github"
					class="flex items-center gap-2 hover:text-fg"
					data-testid="nav-github"
				>
					<Github :size="14" aria-hidden="true" /> GitHub
				</RouterLink>
				<RouterLink
					v-if="session.isAdmin"
					to="/_design"
					class="flex items-center gap-2 hover:text-fg"
					data-testid="nav-design"
				>
					<Palette :size="14" aria-hidden="true" /> Design system
				</RouterLink>
				<span class="truncate font-mono" :title="session.user">{{ session.user }}</span>
			</div>
		</aside>

		<div class="flex min-w-0 flex-col">
			<header
				class="sticky top-0 z-(--ic-z-sticky) flex h-12 items-center gap-4 border-b border-line bg-canvas px-6"
			>
				<h2 class="text-md text-fg-muted">{{ route.meta.title }}</h2>
				<div class="ms-auto flex items-center gap-4">
					<RealtimeIndicator />
					<button
						type="button"
						class="ic-state-layer flex items-center gap-2 rounded border border-line-strong bg-surface-1 px-2.5 py-1 text-xs text-fg-muted"
						data-testid="open-palette"
						@click="palette?.show()"
					>
						<Command :size="12" aria-hidden="true" /> Search <IcKbd>Ctrl</IcKbd
						><IcKbd>K</IcKbd>
					</button>
					<IcIconButton label="Help" size="sm" class="hidden" />
				</div>
			</header>
			<main class="flex-1 px-6 py-6">
				<RouterView v-slot="{ Component }">
					<Transition :name="transitions.fade" mode="out-in">
						<component :is="Component" />
					</Transition>
				</RouterView>
			</main>
		</div>
		<CommandPalette ref="palette" />
	</div>
</template>
