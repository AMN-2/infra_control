<script setup lang="ts">
/**
 * CinematicBackground (ADR 0008): the concert-hall scene behind the login form and the film
 * that carries a confirmed sign-in into the dashboard. Poster first, idle loop once it has a
 * frame, success film once the controller says the session is real. Every media failure
 * degrades to the still poster; the controller's timers keep the dashboard from waiting.
 */
import { computed, onBeforeUnmount, onMounted, ref, useTemplateRef, watch } from "vue";
import { Pause, Play } from "lucide-vue-next";
import { isTabHidden, reducedMotion } from "@/design/motion";
import { pickSources, TIMING } from "./media";
import { useLoginController } from "./useLoginTransition";

const controller = useLoginController();
const state = controller.state;
const sources = pickSources();

const idleEl = useTemplateRef<HTMLVideoElement>("idle");
const successEl = useTemplateRef<HTMLVideoElement>("success");
const idleVisible = ref(false);
const successVisible = ref(false);
const idleUsable = ref(true);
const successUsable = ref(true);
const playing = ref(false);
const userPaused = ref(false);

const withVideo = computed(() => !reducedMotion.value);
const showPauseControl = computed(
	() =>
		withVideo.value &&
		idleUsable.value &&
		idleVisible.value &&
		(state.phase === "idle" || state.phase === "submitting" || state.phase === "mfa")
);
const fadeMs = computed(() => (state.reduced ? TIMING.reducedFadeMs : TIMING.crossfadeMs));

type Cancel = () => void;
/** requestVideoFrameCallback is missing in Firefox; lib.dom types it as always present. */
type MaybeFrameCallback = Omit<
	HTMLVideoElement,
	"requestVideoFrameCallback" | "cancelVideoFrameCallback"
> & {
	requestVideoFrameCallback?: (callback: VideoFrameRequestCallback) => number;
	cancelVideoFrameCallback?: (handle: number) => void;
};

/** Resolve once the element has painted a frame: rVFC where available, else the first timeupdate. */
function whenFrameReady(video: HTMLVideoElement, onFrame: () => void): Cancel {
	const v = video as unknown as MaybeFrameCallback;
	if (typeof v.requestVideoFrameCallback === "function") {
		const handle = v.requestVideoFrameCallback(() => {
			onFrame();
		});
		return () => {
			v.cancelVideoFrameCallback?.(handle);
		};
	}
	const handler = (): void => {
		cleanup();
		onFrame();
	};
	const cleanup = (): void => {
		video.removeEventListener("timeupdate", handler);
		video.removeEventListener("playing", handler);
	};
	video.addEventListener("timeupdate", handler);
	video.addEventListener("playing", handler);
	return cleanup;
}

const cancels: Cancel[] = [];

async function startIdle(): Promise<void> {
	const v = idleEl.value;
	if (!v || !withVideo.value) return;
	v.muted = true;
	cancels.push(
		whenFrameReady(v, () => {
			idleVisible.value = true;
		})
	);
	try {
		await v.play();
		playing.value = true;
	} catch {
		// Autoplay refused or the file cannot play: the poster stays, the form is unaffected.
		idleUsable.value = false;
	}
}

function onIdleError(): void {
	idleUsable.value = false;
	idleVisible.value = false;
}
function onSuccessError(): void {
	successUsable.value = false;
	if (state.phase === "transitioning") controller.successFailed();
}

function togglePause(): void {
	const v = idleEl.value;
	if (!v) return;
	if (playing.value) {
		v.pause();
		playing.value = false;
		userPaused.value = true;
	} else {
		userPaused.value = false;
		v.play()
			.then(() => {
				playing.value = true;
			})
			.catch(() => undefined);
	}
}

watch(isTabHidden, (hidden) => {
	const v = idleEl.value;
	if (!v || !idleUsable.value) return;
	if (hidden) {
		v.pause();
		playing.value = false;
	} else if (!userPaused.value && state.phase !== "done") {
		v.play()
			.then(() => {
				playing.value = true;
			})
			.catch(() => undefined);
	}
});

async function startSuccess(): Promise<void> {
	const v = successEl.value;
	if (!v || state.reduced || !successUsable.value) {
		controller.successFailed();
		return;
	}
	v.muted = true;
	cancels.push(
		whenFrameReady(v, () => {
			successVisible.value = true;
			idleEl.value?.pause();
			controller.successReady();
		})
	);
	const onEnded = (): void => {
		controller.successEnded();
	};
	v.addEventListener("ended", onEnded, { once: true });
	cancels.push(() => {
		v.removeEventListener("ended", onEnded);
	});
	try {
		v.currentTime = 0;
		await v.play();
	} catch {
		controller.successFailed();
	}
}

watch(
	() => state.phase,
	(phase) => {
		if (phase === "transitioning") void startSuccess();
	}
);

function onFadeEnd(event: TransitionEvent): void {
	if (event.propertyName === "opacity" && state.leaving) controller.stageHidden();
}

onMounted(() => {
	void startIdle();
});

onBeforeUnmount(() => {
	for (const cancel of cancels.splice(0)) cancel();
	for (const v of [idleEl.value, successEl.value]) {
		if (!v) continue;
		v.pause();
		v.replaceChildren();
		v.load();
	}
});
</script>

<template>
	<div class="fixed inset-0 z-30" data-testid="cinematic-stage" :data-phase="state.phase">
		<div
			class="scene-backdrop absolute inset-0"
			:class="state.leaving ? 'opacity-0' : 'opacity-100'"
			:style="{ transitionDuration: `${fadeMs}ms` }"
			aria-hidden="true"
			@transitionend.self="onFadeEnd"
		>
			<img
				:src="sources.poster"
				alt=""
				class="absolute inset-0 h-full w-full object-cover"
				decoding="async"
				fetchpriority="high"
				data-testid="scene-poster"
			/>
			<video
				v-if="withVideo"
				ref="idle"
				:poster="sources.poster"
				muted
				playsinline
				loop
				preload="auto"
				disablepictureinpicture
				disableremoteplayback
				tabindex="-1"
				class="scene-layer absolute inset-0 h-full w-full object-cover"
				:class="idleVisible && !successVisible ? 'opacity-100' : 'opacity-0'"
				data-testid="scene-idle"
				@error="onIdleError"
			>
				<source :src="sources.idle" type="video/mp4" />
				<!-- "No playable source" is reported on the last <source>, not on the video. -->
				<source :src="sources.idleWebm" type="video/webm" @error="onIdleError" />
			</video>
			<video
				v-if="withVideo"
				ref="success"
				muted
				playsinline
				preload="auto"
				disablepictureinpicture
				disableremoteplayback
				tabindex="-1"
				class="scene-layer absolute inset-0 h-full w-full object-cover"
				:class="successVisible ? 'opacity-100' : 'opacity-0'"
				data-testid="scene-success"
				@error="onSuccessError"
			>
				<source :src="sources.success" type="video/mp4" />
				<source :src="sources.successWebm" type="video/webm" @error="onSuccessError" />
			</video>
			<!-- Readability: a quiet gradient under the form (bottom on phones, right on wider screens). -->
			<div class="scene-shade absolute inset-0"></div>
		</div>
		<button
			v-show="showPauseControl"
			type="button"
			class="scene-toggle inline-flex h-8 w-8 items-center justify-center rounded-full focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
			:aria-label="playing ? 'Pause background video' : 'Play background video'"
			:aria-pressed="!playing"
			data-testid="scene-toggle"
			@click="togglePause"
		>
			<Pause v-if="playing" class="h-4 w-4" aria-hidden="true" />
			<Play v-else class="h-4 w-4" aria-hidden="true" />
		</button>
	</div>
</template>

<style scoped>
/* Tokens only (design guard): the scene darkens with the app background, never a new colour. */
.scene-backdrop {
	background: var(--ic-canvas);
	transition-property: opacity;
	transition-timing-function: var(--ic-ease);
}
.scene-layer {
	transition: opacity var(--ic-dur-scene) var(--ic-ease);
}
.scene-shade {
	background: linear-gradient(
		to top,
		var(--ic-canvas) 0%,
		var(--ic-canvas) 35%,
		transparent 100%
	);
	opacity: 0.85;
}
@media (min-width: 640px) {
	.scene-shade {
		background: linear-gradient(
			to left,
			var(--ic-canvas) 0%,
			var(--ic-canvas) 28%,
			transparent 72%
		);
		opacity: 0.86;
	}
}
.scene-toggle {
	position: absolute;
	inset-block-start: 1rem;
	inset-inline-end: 1rem;
	z-index: 10;
	border: 1px solid var(--ic-line-strong);
	background: var(--ic-surface-1);
	color: var(--ic-fg-muted);
	opacity: 0.9;
}
@media (min-width: 640px) {
	.scene-toggle {
		inset-block-start: auto;
		inset-inline-end: auto;
		inset-inline-start: 1rem;
		inset-block-end: 1rem;
	}
}
.scene-toggle:hover {
	color: var(--ic-fg);
	opacity: 1;
}
</style>
