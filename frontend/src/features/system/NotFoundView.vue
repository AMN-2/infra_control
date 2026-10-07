<script setup lang="ts">
import { RouterLink } from "vue-router";
import { IcButton, IcEmptyState } from "@/design/components";
</script>

<template>
	<IcEmptyState
		title="Nothing lives at this address"
		description="The link may be stale, or the entity was archived."
	>
		<template #action>
			<RouterLink to="/overview"><IcButton>Back to overview</IcButton></RouterLink>
		</template>
	</IcEmptyState>
</template>
