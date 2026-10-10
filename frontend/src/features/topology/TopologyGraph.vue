<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, useTemplateRef, watch } from "vue";
import { animate } from "motion";
import { Maximize2, Minus, Plus } from "lucide-vue-next";
import { IcIconButton } from "@/design/components";
import { duration, ease, isTabHidden, reducedMotion } from "@/design/motion";
import { pulseEdges, type TopologyLayout, type TopologyNode } from "./layout";
import TopologyNodeCard from "./TopologyNodeCard.vue";

/**
 * The graph itself: SVG edges under absolutely positioned node cards, panned and zoomed with
 * one transform on the stage (§10.3.4). Signature moment: a pulse travels the edges of a server
 * on its heartbeat; nodes with a running job glow. Spatial, so always laid out LTR.
 */
const props = defineProps<{
	layout: TopologyLayout;
	heartbeats: Readonly<Record<string, { ts: string; cpu: number; ram: number; disk: number }>>;
}>();
const emit = defineEmits<{ select: [node: TopologyNode] }>();

// --- viewport -----------------------------------------------------------------------------
const viewport = useTemplateRef<HTMLDivElement>("viewport");
const scale = ref(1);
const tx = ref(0);
const ty = ref(0);
const MIN_SCALE = 0.25;
const MAX_SCALE = 2;
const PADDING = 24;

const stageStyle = computed(() => ({
	transform: `translate(${tx.value}px, ${ty.value}px) scale(${scale.value})`,
	inlineSize: `${props.layout.width}px`,
	blockSize: `${props.layout.height}px`,
}));

function fit(): void {
	const el = viewport.value;
	if (!el || !props.layout.width || !props.layout.height) return;
	const vw = el.clientWidth - PADDING * 2;
	const vh = el.clientHeight - PADDING * 2;
	const s = Math.min(MAX_SCALE, Math.max(MIN_SCALE, vw / props.layout.width, 0), 1);
	const fitted = Math.min(s, vh / props.layout.height || s);
	scale.value = Math.max(MIN_SCALE, fitted);
	tx.value = Math.max(PADDING, (el.clientWidth - props.layout.width * scale.value) / 2);
	ty.value = PADDING;
}

function zoomBy(factor: number, origin?: { x: number; y: number }): void {
	const el = viewport.value;
	const next = Math.min(MAX_SCALE, Math.max(MIN_SCALE, scale.value * factor));
	if (next === scale.value || !el) return;
	const o = origin ?? { x: el.clientWidth / 2, y: el.clientHeight / 2 };
	// Keep the point under the cursor fixed while scaling.
	tx.value = o.x - ((o.x - tx.value) * next) / scale.value;
	ty.value = o.y - ((o.y - ty.value) * next) / scale.value;
	scale.value = next;
}

function onWheel(e: WheelEvent): void {
	e.preventDefault();
	const el = viewport.value;
	if (!el) return;
	const rect = el.getBoundingClientRect();
	zoomBy(e.deltaY < 0 ? 1.1 : 1 / 1.1, { x: e.clientX - rect.left, y: e.clientY - rect.top });
}

let drag: {
	x: number;
	y: number;
	tx: number;
	ty: number;
	moved: boolean;
	pointerId: number;
	el: HTMLElement;
} | null = null;
function onPointerDown(e: PointerEvent): void {
	if (e.button !== 0) return;
	drag = {
		x: e.clientX,
		y: e.clientY,
		tx: tx.value,
		ty: ty.value,
		moved: false,
		pointerId: e.pointerId,
		el: e.currentTarget as HTMLElement,
	};
}
function onPointerMove(e: PointerEvent): void {
	if (!drag) return;
	const dx = e.clientX - drag.x;
	const dy = e.clientY - drag.y;
	if (!drag.moved && Math.abs(dx) + Math.abs(dy) > 3) {
		drag.moved = true;
		// Capture only once this is a pan, so a plain click still reaches the node underneath.
		drag.el.setPointerCapture(drag.pointerId);
	}
	if (!drag.moved) return;
	tx.value = drag.tx + dx;
	ty.value = drag.ty + dy;
}
let panned = false;
function onPointerUp(): void {
	panned = drag?.moved ?? false;
	drag = null;
}
/** A click that ended a pan is not a selection; a keyboard activation always is. */
function select(node: TopologyNode, viaKeyboard = false): void {
	if (panned && !viaKeyboard) {
		panned = false;
		return;
	}
	panned = false;
	emit("select", node);
}

let observer: ResizeObserver | undefined;
onMounted(() => {
	fit();
	if (typeof ResizeObserver !== "undefined" && viewport.value) {
		observer = new ResizeObserver(() => {
			fit();
		});
		observer.observe(viewport.value);
	}
});
onBeforeUnmount(() => {
	observer?.disconnect();
});
watch(
	() => [props.layout.width, props.layout.height],
	() => {
		fit();
	}
);

// --- nodes --------------------------------------------------------------------------------
function metrics(n: TopologyNode): string | null {
	if (n.type !== "server") return null;
	const hb = props.heartbeats[n.ref];
	if (!hb) return null;
	return `cpu ${Math.round(hb.cpu)}% · ram ${Math.round(hb.ram)}% · disk ${Math.round(hb.disk)}%`;
}

// --- heartbeat pulse ----------------------------------------------------------------------
// Dots keyed by edge id: a v-for ref array does not follow source order after edges change.
const pulseDots = new Map<string, SVGCircleElement>();
function setPulseDot(id: string, el: unknown): void {
	if (el instanceof SVGCircleElement) pulseDots.set(id, el);
	else pulseDots.delete(id);
}

/** Lights the server's provider edge and its subtree, one hop at a time (pulseEdges order). */
function pulse(serverRef: string): void {
	const edges = pulseEdges(props.layout, serverRef);
	if (!edges.length) return;
	if (reducedMotion.value || isTabHidden.value) return;
	const depth = new Map<string, number>();
	const sourceDepth = (id: string): number => depth.get(id) ?? 0;
	for (const e of edges) depth.set(e.target, sourceDepth(e.source) + 1);
	const hop = duration.scene * 1.5;
	for (const e of edges) {
		const dot = pulseDots.get(e.id);
		if (!dot) continue;
		animate(
			dot,
			{
				transform: [
					`translate(${e.a.x}px, ${e.a.y}px)`,
					`translate(${e.b.x}px, ${e.b.y}px)`,
				],
				opacity: [0, 1, 1, 0],
			},
			{ duration: hop, ease, delay: sourceDepth(e.source) * hop * 0.6 }
		);
	}
}
defineExpose({ pulse, fit, zoomBy });
</script>

<template>
	<div
		ref="viewport"
		class="relative h-[calc(100dvh-14rem)] min-h-96 touch-none overflow-hidden rounded border border-line bg-canvas select-none"
		dir="ltr"
		data-testid="topology-graph"
		@wheel="onWheel"
		@pointerdown="onPointerDown"
		@pointermove="onPointerMove"
		@pointerup="onPointerUp"
		@pointercancel="onPointerUp"
	>
		<div class="absolute start-0 top-0 origin-top-left" :style="stageStyle">
			<svg
				class="absolute inset-0 overflow-visible"
				:width="layout.width"
				:height="layout.height"
				:viewBox="`0 0 ${layout.width} ${layout.height}`"
				aria-hidden="true"
			>
				<path
					v-for="e in layout.edges"
					:key="e.id"
					:d="e.d"
					class="stroke-line-strong"
					fill="none"
					stroke-width="1"
					vector-effect="non-scaling-stroke"
				/>
				<circle
					v-for="e in layout.edges"
					:key="`pulse-${e.id}`"
					:ref="(el) => setPulseDot(e.id, el)"
					r="3"
					class="fill-healthy"
					opacity="0"
				/>
			</svg>
			<TopologyNodeCard
				v-for="p in layout.nodes"
				:key="p.node.id"
				:node="p.node"
				:x="p.x"
				:y="p.y"
				:metrics="metrics(p.node)"
				@select="select"
			/>
		</div>

		<div
			class="absolute end-3 bottom-3 flex items-center gap-1 rounded border border-line bg-surface-1/90 p-1 backdrop-blur"
			dir="ltr"
		>
			<IcIconButton label="Zoom in" @click="zoomBy(1.25)"
				><Plus class="size-4"
			/></IcIconButton>
			<IcIconButton label="Zoom out" @click="zoomBy(1 / 1.25)">
				<Minus class="size-4" />
			</IcIconButton>
			<IcIconButton label="Fit to view" data-testid="topology-fit" @click="fit()">
				<Maximize2 class="size-4" />
			</IcIconButton>
		</div>
	</div>
</template>
