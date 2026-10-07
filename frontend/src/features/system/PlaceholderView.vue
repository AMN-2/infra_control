<script setup lang="ts">
import { IcCard, IcEmptyState, IcPageHeader } from "@/design/components";

defineProps<{ title: string; description: string; phase: string }>();
</script>

<template>
	<div>
		<IcPageHeader :title="title" />
		<IcCard :padded="false">
			<IcEmptyState :title="`${title} arrives in ${phase}`" :description="description" />
		</IcCard>
	</div>
</template>
