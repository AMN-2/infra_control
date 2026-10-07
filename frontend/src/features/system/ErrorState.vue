<script setup lang="ts">
import { IcButton, IcEmptyState } from "@/design/components";
import type { ApiError } from "@/api/errors";

/** The one error state every screen shows (DoD: loading, empty and error states everywhere). */
withDefaults(defineProps<{ error: ApiError; title?: string }>(), {
	title: "Could not load this view",
});
const emit = defineEmits<{ retry: [] }>();
</script>

<template>
	<IcEmptyState :title="title" :description="`${error.message} (${error.code})`">
		<template #action>
			<IcButton
				variant="secondary"
				data-testid="error-retry"
				@click="
					() => {
						emit('retry');
					}
				"
			>
				Retry
			</IcButton>
		</template>
	</IcEmptyState>
</template>
