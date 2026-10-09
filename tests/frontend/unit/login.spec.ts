import { createPinia, setActivePinia } from "pinia";
import { createMemoryHistory, createRouter } from "vue-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { parseLoginResponse, safeDestination } from "@/api/auth";
import { ApiError } from "@/api/errors";
import type { InfraBoot } from "@/api/boot";
import { createLoginController, type ControllerDeps } from "@/features/login/useLoginTransition";
import { installGuards } from "@/router/guards";
import { routes } from "@/router";
import { useSessionStore } from "@/stores/session";

const BOOT: InfraBoot = {
	csrf_token: "t",
	site_name: "s",
	session_user: "u@x",
	roles: ["Infra Viewer"],
	base_path: "/infra/",
	api_base: "/api/method/infra_control.api.",
	socketio_path: "/socket.io",
	socketio_port: null,
};

function deps(over: Partial<ControllerDeps> = {}) {
	const d = {
		login: vi.fn(() => Promise.resolve({ kind: "ok" } as const)),
		confirmOtp: vi.fn(() => Promise.resolve({ kind: "ok" } as const)),
		fetchBoot: vi.fn(() => Promise.resolve(BOOT)),
		applyBoot: vi.fn(),
		navigate: vi.fn(() => Promise.resolve()),
		onRevealed: vi.fn(),
		reducedMotion: () => false,
		...over,
	};
	return d;
}
const flush = () => vi.advanceTimersByTimeAsync(0);

describe("safeDestination", () => {
	const origin = "https://ops.example";
	it("keeps in-app paths and drops everything else", () => {
		expect(safeDestination("/infra/jobs?status=Failed", origin)).toBe("/jobs?status=Failed");
		expect(safeDestination("/infra", origin)).toBe("/overview");
		expect(safeDestination("/infra/login", origin)).toBe("/overview");
		expect(safeDestination("/app/user", origin)).toBe("/overview");
		expect(safeDestination("https://evil.example/infra/jobs", origin)).toBe("/overview");
		expect(safeDestination("//evil.example/infra", origin)).toBe("/overview");
		expect(safeDestination("/infra/\\evil", origin)).toBe("/overview");
		expect(safeDestination(null, origin)).toBe("/overview");
	});
});

describe("parseLoginResponse", () => {
	it("recognises success, the two-factor step and Frappe's error shapes", () => {
		expect(parseLoginResponse(200, { message: "Logged In", full_name: "A" })).toEqual({
			kind: "ok",
		});
		expect(
			parseLoginResponse(200, {
				verification: { prompt: "Enter <b>code</b>", method: "OTP App" },
				tmp_id: "abc",
			})
		).toEqual({ kind: "mfa", tmpId: "abc", prompt: "Enter code", method: "OTP App" });
		expect(parseLoginResponse(401, { message: "Invalid login credentials" })).toMatchObject({
			kind: "error",
			message: "Invalid email or password.",
		});
		const serverMessages = JSON.stringify([
			JSON.stringify({ message: "User <b>disabled</b>" }),
		]);
		expect(parseLoginResponse(417, { _server_messages: serverMessages })).toMatchObject({
			message: "User disabled",
		});
		expect(parseLoginResponse(200, { message: "Password Reset" })).toMatchObject({
			kind: "error",
		});
	});
});

describe("login transition controller", () => {
	beforeEach(() => {
		vi.useFakeTimers();
	});
	afterEach(() => {
		vi.useRealTimers();
	});

	it("plays the film only after Frappe accepted the login AND the boot confirmed a role", async () => {
		const d = deps({
			fetchBoot: vi.fn(() =>
				Promise.reject(
					new ApiError(403, { code: "permission_denied", message: "no", details: {} })
				)
			),
		});
		const c = createLoginController(d);
		await c.submit({ usr: "u", pwd: "p" });
		expect(c.state.phase).toBe("idle");
		expect(c.state.error).toMatch(/no Infra Control role/);
		expect(d.applyBoot).not.toHaveBeenCalled();
		expect(d.navigate).not.toHaveBeenCalled();
		expect(c.state.stageActive).toBe(false);
	});

	it("rejected credentials stay on the form with the message; nothing navigates", async () => {
		const d = deps({
			login: vi.fn(() =>
				Promise.resolve({
					kind: "error",
					message: "Invalid email or password.",
					status: 401,
				} as const)
			),
		});
		const c = createLoginController(d);
		await c.submit({ usr: "u", pwd: "p" });
		expect(c.state).toMatchObject({
			phase: "idle",
			error: "Invalid email or password.",
			stageActive: false,
		});
		expect(d.fetchBoot).not.toHaveBeenCalled();
	});

	it("happy path: boot applied, film, one navigation, reveal after the film ends", async () => {
		const d = deps();
		const c = createLoginController(d, { destination: "/jobs" });
		await c.submit({ usr: "u", pwd: "p" });
		expect(d.applyBoot).toHaveBeenCalledWith(BOOT);
		expect(c.state.phase).toBe("transitioning");
		expect(c.state.stageActive).toBe(true);
		expect(d.navigate).not.toHaveBeenCalled(); // waits for the film's first frame
		c.successReady();
		c.successReady();
		expect(d.navigate).toHaveBeenCalledTimes(1);
		expect(d.navigate).toHaveBeenCalledWith("/jobs");
		expect(c.state.phase).toBe("transitioning"); // still on the film
		c.successEnded();
		await flush();
		expect(c.state.phase).toBe("done");
		expect(c.state.leaving).toBe(true);
		expect(d.onRevealed).toHaveBeenCalledTimes(1);
		c.stageHidden();
		expect(c.state.stageActive).toBe(false);
		expect(d.navigate).toHaveBeenCalledTimes(1);
	});

	it("a broken film still reveals the dashboard, with one navigation", async () => {
		const d = deps();
		const c = createLoginController(d);
		await c.submit({ usr: "u", pwd: "p" });
		c.successFailed();
		await flush();
		expect(d.navigate).toHaveBeenCalledTimes(1);
		expect(c.state.phase).toBe("done");
	});

	it("a stalled film is bounded by timers: navigate at 1.5 s, reveal by 4 s", async () => {
		const d = deps();
		const c = createLoginController(d);
		await c.submit({ usr: "u", pwd: "p" });
		await vi.advanceTimersByTimeAsync(1500);
		expect(d.navigate).toHaveBeenCalledTimes(1);
		expect(c.state.phase).toBe("transitioning");
		await vi.advanceTimersByTimeAsync(2600);
		expect(c.state.phase).toBe("done");
		await vi.advanceTimersByTimeAsync(1100);
		expect(c.state.stageActive).toBe(false); // the fallback drops the scene even without transitionend
	});

	it("reduced motion skips the film: immediate navigation and a short fade", async () => {
		const d = deps({ reducedMotion: () => true });
		const c = createLoginController(d);
		await c.submit({ usr: "u", pwd: "p" });
		await flush();
		expect(d.navigate).toHaveBeenCalledTimes(1);
		expect(c.state.reduced).toBe(true);
		expect(c.state.phase).toBe("done");
	});

	it("ignores a second submit while one is in flight", async () => {
		let resolve!: (v: { kind: "ok" }) => void;
		const d = deps({ login: vi.fn(() => new Promise<{ kind: "ok" }>((r) => (resolve = r))) });
		const c = createLoginController(d);
		const first = c.submit({ usr: "u", pwd: "p" });
		await c.submit({ usr: "u", pwd: "p" });
		await c.submit({ usr: "u", pwd: "p" });
		expect(d.login).toHaveBeenCalledTimes(1);
		resolve({ kind: "ok" });
		await first;
		expect(c.state.phase).toBe("transitioning");
	});

	it("two-factor: the code goes with the cached attempt id, then the normal path", async () => {
		const d = deps({
			login: vi.fn(() =>
				Promise.resolve({
					kind: "mfa",
					tmpId: "tmp1",
					prompt: "Code?",
					method: "OTP App",
				} as const)
			),
		});
		const c = createLoginController(d);
		await c.submit({ usr: "u", pwd: "p" });
		expect(c.state.phase).toBe("mfa");
		expect(d.fetchBoot).not.toHaveBeenCalled();
		await c.submitOtp("123456");
		expect(d.confirmOtp).toHaveBeenCalledWith("tmp1", "123456");
		expect(c.state.phase).toBe("transitioning");
	});

	it("reset is a no-op mid-transition (a signed-in user is never trapped) and works afterwards", async () => {
		const d = deps();
		const c = createLoginController(d);
		await c.submit({ usr: "u", pwd: "p" });
		c.reset();
		expect(c.state.phase).toBe("transitioning");
		c.successEnded();
		await flush();
		c.stageHidden();
		c.reset();
		expect(c.state.phase).toBe("idle");
	});
});

describe("login route guard", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		delete window.infra_boot;
		vi.stubEnv("DEV", false);
	});
	afterEach(() => {
		vi.unstubAllEnvs();
	});
	function makeRouter() {
		const router = createRouter({ history: createMemoryHistory("/infra/"), routes });
		installGuards(router);
		return router;
	}
	it("lets a guest reach /login and nothing else", async () => {
		window.infra_boot = {
			session_user: "Guest",
			roles: [],
			site_name: "s",
			login_alternatives: true,
		};
		const session = useSessionStore();
		const reauth = vi.spyOn(session, "reauthenticate").mockImplementation(() => undefined);
		const router = makeRouter();
		await router.push("/login");
		expect(router.currentRoute.value.name).toBe("login");
		expect(session.authenticated).toBe(false);
		expect(session.guestBoot?.login_alternatives).toBe(true);
		await router.push("/jobs").catch(() => undefined);
		expect(reauth).toHaveBeenCalled();
	});
	it("sends a signed-in user from /login to the overview", async () => {
		window.infra_boot = { session_user: "v@x", roles: ["Infra Viewer"], site_name: "s" };
		const router = makeRouter();
		await router.push("/login");
		expect(router.currentRoute.value.name).toBe("overview");
	});
});
