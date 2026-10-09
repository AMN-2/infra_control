/**
 * Media for the login scene (ADR 0008, provenance in docs/design/login-media.md). Files live in
 * frontend/public/media/login and ship with the bundle; `import.meta.env.BASE_URL` is the asset
 * base (`/infra/` in dev and preview, `/assets/infra_control/frontend/` in production).
 */
const base = `${import.meta.env.BASE_URL}media/login/`;

export interface SceneSources {
	poster: string;
	/** H.264 MP4 first (hardware decoding everywhere), VP9 WebM for builds without H.264. */
	idle: string;
	idleWebm: string;
	success: string;
	successWebm: string;
}

export const DESKTOP: SceneSources = {
	poster: `${base}conductor-poster.webp`,
	idle: `${base}conductor-idle.mp4`,
	idleWebm: `${base}conductor-idle.webm`,
	success: `${base}conductor-success.mp4`,
	successWebm: `${base}conductor-success.webm`,
};

/** Portrait crop around the conductor for narrow screens. */
export const MOBILE: SceneSources = {
	poster: `${base}conductor-poster-mobile.webp`,
	idle: `${base}conductor-idle-mobile.mp4`,
	idleWebm: `${base}conductor-idle-mobile.webm`,
	success: `${base}conductor-success-mobile.mp4`,
	successWebm: `${base}conductor-success-mobile.webm`,
};

export const LOGO = `${base}smart-choice-logo.png`;

export const MOBILE_QUERY = "(max-width: 640px) and (orientation: portrait)";

export function pickSources(
	matches: boolean = window.matchMedia(MOBILE_QUERY).matches
): SceneSources {
	return matches ? MOBILE : DESKTOP;
}

/** Timings in ms. The film is 2.5 s; every wait is bounded so the dashboard never hangs on media. */
export const TIMING = {
	/** The success film must show a frame within this, else we navigate under the still scene. */
	successReadyMs: 1500,
	/** Hard cap on the whole transition (film + crossfade), counted from the confirmed login. */
	maxTransitionMs: 4000,
	/** Crossfade of the scene into the dashboard. */
	crossfadeMs: 700,
	/** Under reduced motion: a short fade, no film. */
	reducedFadeMs: 200,
} as const;
