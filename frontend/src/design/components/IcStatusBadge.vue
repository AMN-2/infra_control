<script setup lang="ts">
import { computed } from "vue";
import { liveStates, toneFor, type StatusEntity } from "@/design/status";
import IcBadge from "./IcBadge.vue";

const props = defineProps<{ entity: StatusEntity; status: string }>();
const tone = computed(() => toneFor(props.entity, props.status));
const live = computed(() => liveStates.has(props.status));
</script>

<template>
	<IcBadge
		:tone="tone"
		dot
		:live="live"
		:uppercase="entity === 'severity' || entity === 'alert'"
	>
		{{ status }}
	</IcBadge>
</template>
