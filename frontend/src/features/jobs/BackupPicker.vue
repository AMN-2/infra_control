<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { IcInput, IcSelect, IcSkeleton } from "@/design/components";
import { relativeTime } from "@/lib/time";
import { useBackupsStore } from "@/stores/backups";
import { useInventoryStore } from "@/stores/inventory";

/**
 * `x-picker: backup` (A4.2): choose a database backup to restore. Defaults to the target
 * site's backups; "from another site" switches the source to clone a site onto this one.
 */
const props = defineProps<{ site: string; modelValue: string; invalid?: boolean }>();
const emit = defineEmits<{ "update:modelValue": [value: string] }>();
const backups = useBackupsStore();
const inventory = useInventoryStore();
const source = ref(props.site);

const siteOptions = computed(() => [
	{ value: props.site, label: `${props.site} (this site)` },
	...inventory.sites
		.filter((s) => s.domain !== props.site)
		.map((s) => ({ value: s.domain, label: `${s.domain} (clone from)` })),
]);
const options = computed(() =>
	(backups.lists[source.value]?.items ?? [])
		.filter((b) => b.kind === "db")
		.map((b) => ({
			value: b.name,
			label: `${b.name} · ${relativeTime(b.created_at)} · ${Math.round(b.size_mb * 10) / 10} MB`,
		}))
);
watch(source, (s) => {
	emit("update:modelValue", "");
	if (!backups.lists[s]) void backups.fetchList(s, undefined, "db");
});
onMounted(() => {
	if (!backups.lists[props.site]) void backups.fetchList(props.site, undefined, "db");
	if (!inventory.sites.length) void inventory.fetchSites();
});
</script>

<template>
	<div class="flex flex-col gap-3" data-testid="backup-picker">
		<div class="flex flex-col gap-1.5">
			<label for="param-backup-source" class="text-xs font-medium text-fg-muted"
				>Backups of</label
			>
			<IcSelect
				id="param-backup-source"
				v-model="source"
				:options="siteOptions"
				data-testid="backup-source"
			/>
		</div>
		<div class="flex flex-col gap-1.5">
			<label for="param-backup" class="text-xs font-medium text-fg-muted"
				>Database backup <span class="text-down" aria-hidden="true">*</span></label
			>
			<IcSkeleton v-if="backups.loading && !options.length" :lines="1" />
			<IcSelect
				v-else-if="options.length"
				id="param-backup"
				:model-value="modelValue"
				:options="options"
				placeholder="Choose a backup"
				data-testid="backup-select"
				@update:model-value="(v: string) => emit('update:modelValue', v)"
			/>
			<IcInput
				v-else
				id="param-backup"
				:model-value="modelValue"
				mono
				placeholder="BKP-000016"
				:invalid="invalid"
				@update:model-value="(v: string) => emit('update:modelValue', v)"
			/>
			<p v-if="source !== site" class="text-xs text-degraded">
				Restoring another site's backup replaces this site's database with that site's
				data.
			</p>
		</div>
	</div>
</template>
