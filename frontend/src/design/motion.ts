/**
 * Motion presets (plan §10.3). The one easing and the one spring live here; every animation
 * in the app takes its duration, easing and spring from this module or from tokens.css.
 *
 * Rules: animate transform and opacity only; 120 ms press, 200–240 ms transitions, 400 ms max;
 * honour reduced motion; continuous motion only on live things, paused when the tab is hidden.
 */
import { animate, type AnimationPlaybackControls, type DOMKeyframesDefinition } from "motion";
import { readonly, ref } from "vue";

/** Durations in seconds (motion's unit). Mirrors --ic-dur-* in tokens.css. */
export const duration = {
	press: 0.12,
	base: 0.2,
	emphasis: 0.24,
	scene: 0.4,
} as const;

/** The one enter/exit easing. Mirrors --ic-ease. Fast start, long gentle settle. */
export const ease = [0.2, 0, 0, 1] as const;

/** The one spring. Settles visually in `emphasis` time with a hint of overshoot. */
export const spring = {
	type: "spring",
	visualDuration: duration.emphasis,
	bounce: 0.15,
} as const;

/** Travel distances in px, on the 4px grid. Small: motion should hint, not fly. */
export const distance = { sm: 4, md: 8, lg: 16 } as const;

/** Live pulse period in ms. Mirrors --ic-pulse-period. */
export const pulsePeriodMs = 2400;

/** Names of the CSS transition presets in base.css, for <Transition :name>. */
export const transitions = { fade: "ic-fade", rise: "ic-rise", scale: "ic-scale" } as const;

// ---------------------------------------------------------------------------
// Environment: reduced motion and tab visibility
// ---------------------------------------------------------------------------

type MotionOverride = "reduce" | "full" | null;

const systemReduced = ref(false);
const override = ref<MotionOverride>(null);
const reduced = ref(false);
const tabHidden = ref(false);

function syncReduced(): void {
	reduced.value = override.value ? override.value === "reduce" : systemReduced.value;
	const root = document.documentElement;
	if (override.value) root.dataset.motion = override.value;
	else delete root.dataset.motion;
}

/** True when non-essential motion must be skipped. */
export const reducedMotion = readonly(reduced);
/** True while the tab is hidden; continuous animations pause. */
export const isTabHidden = readonly(tabHidden);

/** Force reduced or full motion (the showcase uses this); null follows the OS. */
export function setMotionOverride(value: MotionOverride): void {
	override.value = value;
	syncReduced();
}

let installed = false;
/** Call once at startup. Tracks the OS preference and tab visibility on <html>. */
export function installMotionEnvironment(): void {
	if (installed) return;
	installed = true;
	const query = window.matchMedia("(prefers-reduced-motion: reduce)");
	systemReduced.value = query.matches;
	query.addEventListener("change", (e) => {
		systemReduced.value = e.matches;
		syncReduced();
	});
	syncReduced();

	const syncVisibility = (): void => {
		tabHidden.value = document.visibilityState === "hidden";
		document.documentElement.dataset.visibility = document.visibilityState;
	};
	document.addEventListener("visibilitychange", syncVisibility);
	syncVisibility();
}

// ---------------------------------------------------------------------------
// Presets for imperative animation (motion's animate)
// ---------------------------------------------------------------------------

export interface Preset {
	keyframes: DOMKeyframesDefinition;
	/** Seconds. */
	duration: number;
	/** What remains under reduced motion: opacity only, or nothing at all. */
	reduced: "opacity" | "none";
}

export const presets = {
	/** Something appears in place. */
	fadeIn: { keyframes: { opacity: [0, 1] }, duration: duration.base, reduced: "opacity" },
	/** A new item enters a list or page (alerts, rows, cards). */
	riseIn: {
		keyframes: {
			opacity: [0, 1],
			transform: [`translateY(${distance.md}px)`, "translateY(0)"],
		},
		duration: duration.base,
		reduced: "opacity",
	},
	/** An overlay opens (dialog, palette). Paired with `spring` when it should feel physical. */
	scaleIn: {
		keyframes: { opacity: [0, 1], transform: ["scale(0.96)", "scale(1)"] },
		duration: duration.emphasis,
		reduced: "opacity",
	},
	/** Feedback on press. */
	press: {
		keyframes: { transform: ["scale(1)", "scale(0.97)", "scale(1)"] },
		duration: duration.press * 2,
		reduced: "none",
	},
} as const satisfies Record<string, Preset>;

/** Plays a preset, degrading under reduced motion. */
export function play(
	el: Element,
	preset: Preset,
	options: { delay?: number; useSpring?: boolean } = {}
): AnimationPlaybackControls | null {
	if (reduced.value) {
		if (preset.reduced === "none") return null;
		return animate(el, { opacity: [0, 1] }, { duration: duration.press, ease });
	}
	const timing = options.useSpring ? spring : { duration: preset.duration, ease };
	return animate(el, preset.keyframes, { ...timing, delay: options.delay ?? 0 });
}

/**
 * Wipe-reveal along the inline axis using transforms only: the outer window slides in while
 * the inner content counter-slides, so the content appears drawn without moving. Used for the
 * sparkline draw-in. `outer` must have overflow hidden and contain `inner`.
 */
export function reveal(
	outer: HTMLElement,
	inner: HTMLElement,
	seconds: number = duration.scene
): void {
	if (reduced.value) return;
	const sign = getComputedStyle(outer).direction === "rtl" ? 1 : -1;
	const from = `translateX(${sign * 100}%)`;
	const back = `translateX(${-sign * 100}%)`;
	const timing = { duration: seconds, ease };
	animate(outer, { transform: [from, "translateX(0)"] }, timing);
	animate(inner, { transform: [back, "translateX(0)"] }, timing);
}

/** Counts a number up to `to`, calling `onUpdate` per frame. Instant under reduced motion. */
export function countUp(
	from: number,
	to: number,
	onUpdate: (value: number) => void,
	seconds: number = duration.scene
): AnimationPlaybackControls | null {
	if (reduced.value || from === to) {
		onUpdate(to);
		return null;
	}
	return animate(from, to, { duration: seconds, ease, onUpdate });
}
