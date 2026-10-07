<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, useTemplateRef } from "vue";
import { animate } from "motion";
import ShowcaseSection from "../ShowcaseSection.vue";
import Sparkline from "../Sparkline.vue";
import { countUp, duration, ease, isTabHidden, reducedMotion, transitions } from "@/design/motion";
import { spaceUnitPx } from "@/design/tokens";
import type { Tone } from "@/design/status";

// Sample data for the showcase only. Real screens read stores fed by the API.

// --- Overview: numbers count up, sparklines draw in -------------------------
const stats = [
	{
		label: "Servers",
		value: 18,
		tone: "healthy",
		note: "17 active · 1 degraded",
		points: [14, 14, 15, 15, 16, 16, 16, 17, 18, 18],
	},
	{
		label: "Sites",
		value: 142,
		tone: "healthy",
		note: "3 in maintenance",
		points: [118, 121, 124, 126, 129, 131, 134, 137, 140, 142],
	},
	{
		label: "Running jobs",
		value: 3,
		tone: "running",
		note: "1 bulk rollout",
		points: [1, 0, 2, 4, 3, 1, 2, 5, 4, 3],
	},
	{
		label: "Firing alerts",
		value: 1,
		tone: "down",
		note: "Disk on erp-prod-02",
		points: [0, 0, 1, 0, 0, 2, 1, 0, 0, 1],
	},
] as const satisfies readonly {
	label: string;
	value: number;
	tone: Tone;
	note: string;
	points: number[];
}[];

const shown = ref(stats.map(() => 0));
const run = ref(0);

function playOverview(): void {
	run.value++;
	stats.forEach((s, i) => {
		countUp(0, s.value, (v) => {
			shown.value[i] = Math.round(v);
		});
	});
}

const toneText: Record<Tone, string> = {
	healthy: "text-healthy",
	degraded: "text-degraded",
	down: "text-down",
	running: "text-running",
	neutral: "text-neutral",
};

// --- Topology: heartbeat pulse travels edges; running jobs glow --------------
// Coordinates in 4px grid units; the diagram is spatial, so it is always laid out LTR.
const u = spaceUnitPx;
const node = { w: 32, h: 11 };
const nodes = [
	{ id: "do", label: "DigitalOcean", kind: "Provider", x: 0, y: 22 },
	{ id: "srv", label: "erp-prod-02", kind: "Server", x: 46, y: 22 },
	{ id: "s1", label: "acme.erp.io", kind: "Site", x: 96, y: 2 },
	{ id: "s2", label: "beta.erp.io", kind: "Site", x: 96, y: 22 },
	{ id: "s3", label: "gamma.erp.io", kind: "Site", x: 96, y: 42 },
] as const;
type NodeId = (typeof nodes)[number]["id"];
const edges: [NodeId, NodeId][] = [
	["srv", "do"],
	["srv", "s1"],
	["srv", "s2"],
	["srv", "s3"],
];
const W = 128;
const H = 55;

function anchor(id: NodeId, side: "in" | "out"): { x: number; y: number } {
	const n = nodes.find((m) => m.id === id);
	if (!n) return { x: 0, y: 0 };
	return { x: (side === "out" ? n.x + node.w : n.x) * u, y: (n.y + node.h / 2) * u };
}
/** Edges are drawn left to right; the pulse direction is from → to (server outwards). */
const edgeGeometry = edges.map(([from, to]) => {
	const leftToRight =
		nodes.findIndex((n) => n.id === from) < nodes.findIndex((n) => n.id === to);
	const a = leftToRight ? anchor(from, "out") : anchor(from, "in");
	const b = leftToRight ? anchor(to, "in") : anchor(to, "out");
	return { key: `${from}-${to}`, a, b };
});

const jobRunning = ref(true);
const lastBeat = ref(0);
const now = ref(Date.now());
const pulses = useTemplateRef<SVGCircleElement[]>("pulse");

function beat(): void {
	lastBeat.value = Date.now();
	if (reducedMotion.value) return;
	edgeGeometry.forEach((e, i) => {
		const dot = pulses.value?.[i];
		if (!dot) return;
		animate(
			dot,
			{
				transform: [
					`translate(${e.a.x}px, ${e.a.y}px)`,
					`translate(${e.b.x}px, ${e.b.y}px)`,
				],
				opacity: [0, 1, 1, 0],
			},
			{ duration: duration.scene * 2, ease }
		);
	});
}

// --- Alerts: a new alert slides in with its severity accent -----------------
interface DemoAlert {
	id: number;
	title: string;
	target: string;
	severity: "critical" | "warning";
}
const alertPool: Omit<DemoAlert, "id">[] = [
	{ title: "No heartbeat for 3 minutes", target: "db-01", severity: "critical" },
	{
		title: "SSL certificate expires in 9 days",
		target: "acme.example.com",
		severity: "warning",
	},
	{ title: "Queue backlog above 500", target: "erp-prod-02", severity: "warning" },
	{ title: "Disk usage 91%", target: "erp-prod-02", severity: "critical" },
];
let nextId = 2;
const alerts = ref<DemoAlert[]>([
	{ id: 1, title: "Disk usage 91%", target: "erp-prod-02", severity: "critical" },
	{
		id: 0,
		title: "Restore test older than 35 days",
		target: "beta.example.com",
		severity: "warning",
	},
]);
function fireAlert(): void {
	const sample = alertPool[nextId % alertPool.length];
	if (!sample) return;
	alerts.value = [{ ...sample, id: nextId++ }, ...alerts.value].slice(0, 4);
}

let beatTimer: ReturnType<typeof setInterval> | undefined;
let clockTimer: ReturnType<typeof setInterval> | undefined;
onMounted(() => {
	playOverview();
	beat();
	// Simulated heartbeat; real ones arrive as infra:server.heartbeat. Paused while hidden.
	beatTimer = setInterval(() => {
		if (!isTabHidden.value) beat();
	}, 3000);
	clockTimer = setInterval(() => (now.value = Date.now()), 1000);
});
onBeforeUnmount(() => {
	clearInterval(beatTimer);
	clearInterval(clockTimer);
});
</script>

<template>
	<ShowcaseSection
		id="moments"
		title="Signature moments"
		lead="Previews of the one moment each screen is built around (plan §10.2), made only from the tokens and presets below. They use sample data."
	>
		<div class="flex flex-col gap-6">
			<!-- Overview -->
			<div class="rounded border border-line bg-surface-1 p-6">
				<div class="mb-5 flex items-center justify-between">
					<div>
						<h3 class="text-md">Overview: numbers count up, sparklines draw in</h3>
						<p class="text-xs text-fg-subtle">
							Plays once on arrival ({{ duration.scene * 1000 }} ms) and never loops.
							Under reduced motion the final numbers appear immediately.
						</p>
					</div>
					<button
						type="button"
						class="ic-state-layer rounded border border-line-strong px-3 py-1.5 text-xs"
						data-testid="replay-overview"
						@click="playOverview"
					>
						Replay
					</button>
				</div>
				<div class="grid grid-cols-4 gap-3">
					<div
						v-for="(s, i) in stats"
						:key="s.label"
						class="flex flex-col gap-3 rounded border border-line bg-surface-2 p-4"
					>
						<span class="eyebrow">{{ s.label }}</span>
						<span
							class="numerals text-3xl font-medium leading-none"
							data-testid="stat-value"
						>
							{{ shown[i] }}
						</span>
						<Sparkline :key="run" :points="s.points" :tone="s.tone" />
						<span class="text-xs" :class="toneText[s.tone]">{{ s.note }}</span>
					</div>
				</div>
			</div>

			<div class="grid grid-cols-[minmax(0,3fr)_minmax(0,2fr)] gap-6">
				<!-- Topology -->
				<div class="rounded border border-line bg-surface-1 p-6">
					<div class="mb-5 flex items-start justify-between gap-4">
						<div>
							<h3 class="text-md">Topology: heartbeat pulse, running job glows</h3>
							<p class="text-xs text-fg-subtle">
								Heartbeat {{ Math.max(0, Math.round((now - lastBeat) / 1000)) }} s
								ago. Pauses while the tab is hidden.
							</p>
						</div>
						<button
							type="button"
							class="ic-state-layer shrink-0 rounded border border-line-strong px-3 py-1.5 text-xs"
							data-testid="toggle-job"
							@click="jobRunning = !jobRunning"
						>
							{{ jobRunning ? "Finish job" : "Start job" }}
						</button>
					</div>
					<div class="overflow-x-auto">
						<div
							class="relative"
							dir="ltr"
							:style="{ inlineSize: `${W * u}px`, blockSize: `${H * u}px` }"
						>
							<svg
								class="absolute inset-0 overflow-visible"
								:viewBox="`0 0 ${W * u} ${H * u}`"
								:width="W * u"
								:height="H * u"
								aria-hidden="true"
							>
								<path
									v-for="e in edgeGeometry"
									:key="e.key"
									:d="`M${e.a.x},${e.a.y} C${(e.a.x + e.b.x) / 2},${e.a.y} ${(e.a.x + e.b.x) / 2},${e.b.y} ${e.b.x},${e.b.y}`"
									class="stroke-line-strong"
									fill="none"
								/>
								<circle
									v-for="e in edgeGeometry"
									ref="pulse"
									:key="`p-${e.key}`"
									r="3"
									class="fill-healthy"
									opacity="0"
								/>
							</svg>
							<div
								v-for="n in nodes"
								:key="n.id"
								class="absolute flex flex-col justify-center rounded border bg-surface-2 px-3"
								:class="[
									n.id === 'srv' && jobRunning
										? 'ic-glow border-running'
										: 'border-line-strong',
								]"
								:style="{
									insetInlineStart: `${n.x * u}px`,
									insetBlockStart: `${n.y * u}px`,
									inlineSize: `${node.w * u}px`,
									blockSize: `${node.h * u}px`,
								}"
								:data-testid="`node-${n.id}`"
							>
								<span class="flex items-center gap-1.5 truncate text-xs">
									<span
										class="size-1.5 shrink-0 rounded-full"
										:class="
											n.id === 'srv' && jobRunning
												? 'ic-pulse bg-running text-running'
												: 'bg-healthy'
										"
									/>
									<span
										class="truncate"
										:class="
											n.kind === 'Provider' ? 'font-medium' : 'font-mono'
										"
										>{{ n.label }}</span
									>
								</span>
								<span class="text-2xs text-fg-subtle">{{ n.kind }}</span>
							</div>
						</div>
					</div>
				</div>

				<!-- Alerts -->
				<div class="flex flex-col rounded border border-line bg-surface-1 p-6">
					<div class="mb-5 flex items-start justify-between gap-4">
						<div>
							<h3 class="text-md">Alerts: new alert slides in</h3>
							<p class="text-xs text-fg-subtle">
								The severity accent marks the alert, not the whole row.
							</p>
						</div>
						<button
							type="button"
							class="ic-state-layer shrink-0 rounded border border-line-strong px-3 py-1.5 text-xs"
							data-testid="fire-alert"
							@click="fireAlert"
						>
							Fire alert
						</button>
					</div>
					<TransitionGroup
						tag="ul"
						:name="transitions.rise"
						class="flex flex-col gap-2"
						aria-live="polite"
						data-testid="alert-list"
					>
						<li
							v-for="a in alerts"
							:key="a.id"
							class="flex items-center gap-3 rounded-sm border border-line border-s-2 bg-surface-2 px-3 py-2.5"
							:class="
								a.severity === 'critical' ? 'border-s-down' : 'border-s-degraded'
							"
						>
							<div class="flex min-w-0 flex-col">
								<span class="truncate">{{ a.title }}</span>
								<span class="truncate font-mono text-xs text-fg-subtle">{{
									a.target
								}}</span>
							</div>
							<span
								class="ms-auto shrink-0 rounded-full px-2 py-0.5 text-2xs font-medium uppercase tracking-wide"
								:class="
									a.severity === 'critical'
										? 'bg-down-soft text-down'
										: 'bg-degraded-soft text-degraded'
								"
							>
								{{ a.severity }}
							</span>
						</li>
					</TransitionGroup>
				</div>
			</div>
		</div>
	</ShowcaseSection>
</template>
