/**
 * LoginTransitionController (ADR 0008): the lifecycle from the form to the dashboard.
 *
 *   idle → submitting → (mfa → submitting) → authenticated → transitioning → done
 *
 * Only a confirmed session (Frappe accepted the credentials AND `session.boot` returned the
 * roles) moves past `authenticated`. Media never gates sign-in: every wait on the film is
 * bounded, a failed or missing video shortens the transition to a plain fade, and reduced
 * motion skips the film altogether. The scene component drives the media and reports back
 * through `successReady`, `successEnded`, `successFailed` and `stageHidden`.
 */
import { reactive, readonly } from "vue";
import type { InfraBoot } from "@/api/boot";
import type { Credentials, LoginResult } from "@/api/auth";
import { ApiError } from "@/api/errors";
import { TIMING } from "./media";

export type Phase = "idle" | "submitting" | "mfa" | "authenticated" | "transitioning" | "done";

export interface MfaStep {
	tmpId: string;
	prompt: string;
	method: string;
}

export interface TransitionState {
	phase: Phase;
	error: string | null;
	mfa: MfaStep | null;
	/** Router path (relative to /infra) the user ends up on. */
	destination: string;
	/** The scene stays mounted while true, across the route change into the dashboard. */
	stageActive: boolean;
	/** The scene is fading out over the dashboard. */
	leaving: boolean;
	/** Under reduced motion the film is skipped: fade only. */
	reduced: boolean;
}

export interface ControllerDeps {
	login: (credentials: Credentials) => Promise<LoginResult>;
	confirmOtp: (tmpId: string, otp: string) => Promise<LoginResult>;
	fetchBoot: () => Promise<InfraBoot>;
	/** Store the boot data and start the authenticated services. */
	applyBoot: (boot: InfraBoot) => void;
	/** router.push; resolves once the destination route rendered. */
	navigate: (destination: string) => Promise<unknown>;
	/** Called once the dashboard is revealed, to move focus into it. */
	onRevealed?: () => void;
	reducedMotion: () => boolean;
	setTimeout?: (fn: () => void, ms: number) => unknown;
	clearTimeout?: (id: unknown) => void;
}

export interface LoginController {
	readonly state: Readonly<TransitionState>;
	submit: (credentials: Credentials) => Promise<void>;
	submitOtp: (otp: string) => Promise<void>;
	/** The film has produced its first frame (the idle layer can go). */
	successReady: () => void;
	/** The film finished playing. */
	successEnded: () => void;
	/** The film cannot play (missing file, decode error, autoplay refused, stalled). */
	successFailed: () => void;
	/** The scene finished fading out and can unmount. */
	stageHidden: () => void;
	/** Prepare for a new attempt (route left, component unmounted). Never traps a signed-in user. */
	reset: () => void;
	/** Validated router path (see `safeDestination`) to reveal after sign-in. */
	setDestination: (path: string) => void;
}

const NO_ACCESS = "Signed in, but this account has no Infra Control role. Ask an Infra Admin.";

export function createLoginController(
	deps: ControllerDeps,
	initial: Partial<Pick<TransitionState, "destination">> = {}
): LoginController {
	const setTimer =
		deps.setTimeout ?? ((fn: () => void, ms: number) => globalThis.setTimeout(fn, ms));
	const clearTimer =
		deps.clearTimeout ??
		((id: unknown) => {
			globalThis.clearTimeout(id as ReturnType<typeof globalThis.setTimeout>);
		});
	const state = reactive<TransitionState>({
		phase: "idle",
		error: null,
		mfa: null,
		destination: initial.destination ?? "/overview",
		stageActive: false,
		leaving: false,
		reduced: false,
	});
	let attempt = 0; // bumps on reset so stale responses are ignored
	let navigated = false;
	let navigation: Promise<unknown> | null = null;
	let ended = false;
	let finishing = false;
	const timers: unknown[] = [];

	function later(fn: () => void, ms: number): void {
		timers.push(setTimer(fn, ms));
	}
	function clearTimers(): void {
		for (const t of timers.splice(0)) clearTimer(t);
	}

	async function complete(result: LoginResult, token: number): Promise<void> {
		if (token !== attempt) return;
		if (result.kind === "mfa") {
			state.mfa = { tmpId: result.tmpId, prompt: result.prompt, method: result.method };
			state.phase = "mfa";
			return;
		}
		if (result.kind === "error") {
			state.error = result.message;
			state.phase = state.mfa ? "mfa" : "idle";
			return;
		}
		let boot: InfraBoot;
		try {
			boot = await deps.fetchBoot();
		} catch (err) {
			if (token !== attempt) return;
			state.error =
				err instanceof ApiError && err.status === 403
					? NO_ACCESS
					: "Signed in, but the session could not be loaded. Reload and try again.";
			state.phase = "idle";
			state.mfa = null;
			return;
		}
		if (token !== attempt) return;
		deps.applyBoot(boot);
		state.phase = "authenticated";
		state.mfa = null;
		begin();
	}

	function begin(): void {
		if (state.phase !== "authenticated") return;
		state.reduced = deps.reducedMotion();
		state.stageActive = true;
		state.phase = "transitioning";
		if (state.reduced) {
			// No film: the still scene fades into the dashboard.
			navigateOnce();
			finish();
			return;
		}
		later(() => {
			if (!navigated) navigateOnce(); // the film is late: reveal under the still scene
		}, TIMING.successReadyMs);
		later(() => {
			if (!finishing) finish();
		}, TIMING.maxTransitionMs);
	}

	function navigateOnce(): void {
		if (navigated) return;
		navigated = true;
		navigation = deps.navigate(state.destination).catch(() => undefined);
	}

	function finish(): void {
		if (finishing) return;
		finishing = true;
		clearTimers();
		navigateOnce();
		// Reveal only once the destination route rendered, so the crossfade lands on real UI.
		void (navigation ?? Promise.resolve()).then(() => {
			state.leaving = true;
			state.phase = "done";
			deps.onRevealed?.();
			// Belt and braces: if the scene never reports the end of its fade, drop it anyway.
			later(stageHidden, (state.reduced ? TIMING.reducedFadeMs : TIMING.crossfadeMs) + 300);
		});
	}

	function stageHidden(): void {
		clearTimers();
		state.stageActive = false;
		state.leaving = false;
	}

	return {
		state: readonly(state),
		async submit(credentials) {
			if (state.phase !== "idle") return; // one request at a time
			state.error = null;
			state.phase = "submitting";
			const token = attempt;
			const result = await deps.login(credentials);
			await complete(result, token);
		},
		async submitOtp(otp) {
			if (state.phase !== "mfa" || !state.mfa) return;
			state.error = null;
			state.phase = "submitting";
			const token = attempt;
			const result = await deps.confirmOtp(state.mfa.tmpId, otp);
			await complete(result, token);
		},
		successReady() {
			if (state.phase !== "transitioning") return;
			navigateOnce();
		},
		successEnded() {
			if (state.phase !== "transitioning" || ended) return;
			ended = true;
			finish();
		},
		successFailed() {
			if (state.phase !== "transitioning") return;
			finish();
		},
		stageHidden,
		reset() {
			// Never trap a signed-in user: a running or still-visible transition completes.
			if (state.phase === "transitioning" || state.stageActive) return;
			attempt += 1;
			clearTimers();
			navigated = false;
			navigation = null;
			ended = false;
			finishing = false;
			state.phase = "idle";
			state.error = null;
			state.mfa = null;
			state.leaving = false;
		},
		setDestination(path) {
			state.destination = path;
		},
	};
}

// ---------------------------------------------------------------------------
// The app's single controller, shared by App.vue (stage), LoginView and the form.
// ---------------------------------------------------------------------------
import { confirmOtp, fetchBoot, login } from "@/api/auth";
import { startAuthenticatedServices } from "@/app/bootstrap";
import { reducedMotion } from "@/design/motion";
import { router } from "@/router";
import { useSessionStore } from "@/stores/session";

let controller: LoginController | null = null;

/** Moves focus into the dashboard once the scene has revealed it. */
function focusDashboard(): void {
	const main = document.querySelector<HTMLElement>('[data-testid="app-shell"] main');
	if (!main) return;
	main.tabIndex = -1;
	main.focus({ preventScroll: true });
}

export function useLoginController(): LoginController {
	if (controller) return controller;
	const session = useSessionStore();
	controller = createLoginController({
		login,
		confirmOtp,
		fetchBoot,
		applyBoot: (boot) => {
			session.applyBoot(boot);
			startAuthenticatedServices();
		},
		navigate: (destination) => router.push(destination),
		onRevealed: focusDashboard,
		reducedMotion: () => reducedMotion.value,
	});
	return controller;
}

/** Tests only. */
export function _setLoginControllerForTests(next: LoginController | null): void {
	controller = next;
}
