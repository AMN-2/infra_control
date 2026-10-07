<script setup lang="ts">
import { providerLabel, type Provider } from "@/design/status";

withDefaults(defineProps<{ provider: Provider; long?: boolean }>(), { long: false });
</script>

<template>
	<span
		class="inline-flex shrink-0 items-center rounded-sm border border-line-strong bg-surface-2 px-1.5 py-px font-mono text-2xs tracking-wide text-fg-muted uppercase"
		:title="providerLabel[provider].long"
	>
		{{ long ? providerLabel[provider].long : providerLabel[provider].short }}
	</span>
</template>
