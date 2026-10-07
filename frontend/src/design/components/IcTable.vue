<script setup lang="ts" generic="T extends Record<string, unknown>">
import IcSkeleton from "./IcSkeleton.vue";
import IcEmptyState from "./IcEmptyState.vue";

export interface Column<Row> {
	key: keyof Row & string;
	label: string;
	align?: "start" | "end";
	mono?: boolean;
	width?: string;
}
const props = withDefaults(
	defineProps<{
		columns: readonly Column<T>[];
		rows: readonly T[];
		rowKey: keyof T;
		loading?: boolean;
		emptyTitle?: string;
		emptyDescription?: string;
		clickable?: boolean;
		selected?: string;
	}>(),
	{
		loading: false,
		emptyTitle: "Nothing here yet",
		emptyDescription: undefined,
		clickable: false,
		selected: undefined,
	}
);
const emit = defineEmits<{ rowClick: [row: T] }>();

function keyOf(row: T): string {
	return String(row[props.rowKey]);
}
function cell(row: T, key: keyof T): string {
	const v = row[key];
	if (v === null || v === undefined) return "";
	if (typeof v === "string") return v;
	if (typeof v === "number" || typeof v === "boolean" || typeof v === "bigint") return String(v);
	return JSON.stringify(v);
}
</script>

<template>
	<div class="overflow-x-auto rounded border border-line bg-surface-1">
		<table class="w-full border-collapse text-sm">
			<thead>
				<tr class="border-b border-line">
					<th
						v-for="c in columns"
						:key="c.key"
						scope="col"
						class="eyebrow px-4 py-2.5 font-medium"
						:class="c.align === 'end' ? 'text-end' : 'text-start'"
						:style="c.width ? { inlineSize: c.width } : undefined"
					>
						{{ c.label }}
					</th>
				</tr>
			</thead>
			<tbody v-if="loading">
				<tr v-for="i in 5" :key="i" class="border-b border-line last:border-b-0">
					<td v-for="c in columns" :key="c.key" class="px-4 py-3">
						<IcSkeleton />
					</td>
				</tr>
			</tbody>
			<tbody v-else-if="rows.length === 0">
				<tr>
					<td :colspan="columns.length">
						<IcEmptyState :title="emptyTitle" :description="emptyDescription" />
					</td>
				</tr>
			</tbody>
			<tbody v-else>
				<tr
					v-for="row in rows"
					:key="keyOf(row)"
					class="border-b border-line last:border-b-0"
					:class="[
						{ 'ic-state-layer cursor-pointer': clickable },
						selected === keyOf(row) ? 'bg-surface-2' : '',
					]"
					:tabindex="clickable ? 0 : undefined"
					:aria-selected="selected === keyOf(row) || undefined"
					@click="clickable && emit('rowClick', row)"
					@keydown.enter="clickable && emit('rowClick', row)"
				>
					<td
						v-for="c in columns"
						:key="c.key"
						class="px-4 py-2.5 align-middle"
						:class="[
							c.align === 'end' ? 'text-end' : 'text-start',
							{ 'font-mono text-xs': c.mono },
						]"
					>
						<slot :name="`cell-${c.key}`" :row="row" :value="row[c.key]">
							{{ cell(row, c.key) }}
						</slot>
					</td>
				</tr>
			</tbody>
		</table>
	</div>
</template>
