import { test as base, expect, type Page, type Route } from "@playwright/test";
import { injectBoot } from "./fixtures";

/**
 * The in-app login (ADR 0008) against `vite preview` + the Prism mock: `session.boot` comes from
 * the contract example; Frappe's `/api/method/login` is not part of the contract, so each test
 * mocks it. The bundled Chromium has no H.264 decoder, so the MP4s fail and the WebM fallbacks
 * carry the scene; the "missing video" test aborts both.
 */
const test = base.extend({
	page: async ({ page }, use) => {
		await page.addInitScript(() => {
			window.infra_boot = {
				site_name: "e2e.localhost",
				session_user: "Guest",
				roles: [],
				base_path: "/infra/",
				api_base: "/api/method/infra_control.api.",
				socketio_path: "/socket.io",
				login_alternatives: true,
			};
		});
		await use(page);
	},
});

type Answer = (route: Route, body: Record<string, string>) => Promise<void>;
const ok: Answer = (route) =>
	route.fulfill({
		status: 200,
		contentType: "application/json",
		body: JSON.stringify({ message: "Logged In", full_name: "E2E", home_page: "/infra" }),
	});
const invalid: Answer = (route) =>
	route.fulfill({
		status: 401,
		contentType: "application/json",
		body: JSON.stringify({
			message: "Invalid login credentials",
			exc_type: "AuthenticationError",
		}),
	});

async function mockLogin(page: Page, answer: Answer): Promise<Record<string, string>[]> {
	const calls: Record<string, string>[] = [];
	await page.route("**/api/method/login", async (route) => {
		const body = route.request().postDataJSON() as Record<string, string>;
		calls.push(body);
		await answer(route, body);
	});
	return calls;
}

async function fill(page: Page, email = "ameen@example.com", pwd = "secret") {
	await page.getByLabel("Email").fill(email);
	await page.locator("#login-password").fill(pwd);
}

test.describe("in-app login", () => {
	test("signs in, plays the scene once and reveals the overview with a single navigation", async ({
		page,
	}) => {
		const calls = await mockLogin(page, ok);
		await page.goto("./login");
		await expect(page).toHaveTitle("Sign in · Infra Control");
		await expect(page.getByTestId("cinematic-stage")).toHaveAttribute("data-phase", "idle");
		await expect(page.getByTestId("scene-poster")).toBeVisible();
		await fill(page);
		await page.getByTestId("login-submit").click();
		await expect(page).toHaveURL(/\/infra\/overview$/);
		await expect(page.getByTestId("app-shell")).toBeVisible();
		await expect(page.getByTestId("cinematic-stage")).toHaveCount(0, { timeout: 8000 });
		expect(calls).toHaveLength(1);
		expect(calls[0]).toEqual({ usr: "ameen@example.com", pwd: "secret" });
		// The password never lands in storage.
		const stored = await page.evaluate(() => JSON.stringify([localStorage, sessionStorage]));
		expect(stored).not.toContain("secret");
		// A refresh never replays the film: with the guest boot the guard sends us back to the
		// form, which starts idle; with a real session the dashboard renders without a stage.
		await page.reload();
		await expect(page).toHaveURL(/\/infra\/login\?redirect-to=/);
		await expect(page.getByTestId("cinematic-stage")).toHaveAttribute("data-phase", "idle");
	});

	test("invalid credentials: error announced, email kept, controls restored, no film", async ({
		page,
	}) => {
		await mockLogin(page, invalid);
		await page.goto("./login");
		await fill(page, "ameen@example.com", "wrong");
		await page.getByTestId("login-submit").click();
		const alert = page.getByRole("alert");
		await expect(alert).toHaveText("Invalid email or password.");
		await expect(page.getByLabel("Email")).toHaveValue("ameen@example.com");
		await expect(page.getByTestId("login-submit")).toBeEnabled();
		await expect(page.locator("#login-password")).toBeFocused();
		await expect(page.getByTestId("cinematic-stage")).toHaveAttribute("data-phase", "idle");
		await expect(page).toHaveURL(/\/infra\/login$/);
	});

	test("slow authentication: repeated clicks send one request and the button shows progress", async ({
		page,
	}) => {
		const calls = await mockLogin(page, async (route) => {
			await new Promise((r) => setTimeout(r, 1200));
			await ok(route, {});
		});
		await page.goto("./login");
		await fill(page);
		const submit = page.getByTestId("login-submit");
		await submit.click();
		await expect(submit).toHaveAttribute("aria-busy", "true");
		await submit.click({ force: true }).catch(() => undefined);
		await page.keyboard.press("Enter");
		await expect(page).toHaveURL(/\/infra\/overview$/, { timeout: 10000 });
		expect(calls).toHaveLength(1);
	});

	test("missing video files: the still scene fades and the dashboard still appears", async ({
		page,
	}) => {
		await mockLogin(page, ok);
		await page.route("**/media/login/*.mp4", (route) => route.abort());
		await page.route("**/media/login/*.webm", (route) => route.abort());
		await page.goto("./login");
		await expect(page.getByTestId("scene-poster")).toBeVisible();
		await expect(page.getByTestId("scene-toggle")).toBeHidden();
		await fill(page);
		await page.getByTestId("login-submit").click();
		await expect(page).toHaveURL(/\/infra\/overview$/);
		await expect(page.getByTestId("cinematic-stage")).toHaveCount(0, { timeout: 8000 });
	});

	test("autoplay refused: poster stays, sign-in unaffected", async ({ page }) => {
		await page.addInitScript(() => {
			HTMLMediaElement.prototype.play = () =>
				Promise.reject(new DOMException("NotAllowedError"));
		});
		await mockLogin(page, ok);
		await page.goto("./login");
		await expect(page.getByTestId("scene-poster")).toBeVisible();
		await expect(page.getByTestId("scene-toggle")).toBeHidden();
		await fill(page);
		await page.getByTestId("login-submit").click();
		await expect(page).toHaveURL(/\/infra\/overview$/);
		await expect(page.getByTestId("cinematic-stage")).toHaveCount(0, { timeout: 8000 });
	});

	test("reduced motion: no video elements, a short fade into the dashboard", async ({
		page,
	}) => {
		await page.emulateMedia({ reducedMotion: "reduce" });
		await mockLogin(page, ok);
		await page.goto("./login");
		await expect(page.getByTestId("scene-poster")).toBeVisible();
		await expect(page.getByTestId("scene-idle")).toHaveCount(0);
		await fill(page);
		await page.getByTestId("login-submit").click();
		await expect(page).toHaveURL(/\/infra\/overview$/);
		await expect(page.getByTestId("cinematic-stage")).toHaveCount(0, { timeout: 4000 });
	});

	test("mobile: portrait crop, form reachable by keyboard", async ({ page }) => {
		await page.setViewportSize({ width: 390, height: 844 });
		await mockLogin(page, ok);
		await page.goto("./login");
		await expect(page.getByTestId("scene-poster")).toHaveAttribute(
			"src",
			/conductor-poster-mobile\.webp$/
		);
		await expect(page.getByLabel("Email")).toBeFocused();
		await page.keyboard.type("ameen@example.com");
		await page.keyboard.press("Tab");
		await expect(page.locator("#login-password")).toBeFocused();
		await page.keyboard.type("secret");
		await page.keyboard.press("Enter");
		await expect(page).toHaveURL(/\/infra\/overview$/);
	});

	test("two-factor step, then the dashboard", async ({ page }) => {
		const calls = await mockLogin(page, async (route, body) => {
			if (body.otp) {
				await ok(route, body);
				return;
			}
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({
					verification: { prompt: "Enter the code from your app", method: "OTP App" },
					tmp_id: "tmp42",
				}),
			});
		});
		await page.goto("./login");
		await fill(page);
		await page.getByTestId("login-submit").click();
		await expect(page.getByRole("heading", { name: "Verify it's you" })).toBeVisible();
		await expect(page.getByLabel("Verification code")).toBeFocused();
		await page.keyboard.type("123456");
		await page.keyboard.press("Enter");
		await expect(page).toHaveURL(/\/infra\/overview$/);
		expect(calls[1]).toEqual({ tmp_id: "tmp42", otp: "123456" });
	});

	test("redirect-to is honoured only for same-origin app paths", async ({ page }) => {
		await mockLogin(page, ok);
		await page.goto("./login?redirect-to=%2Finfra%2Fjobs");
		await fill(page);
		await page.getByTestId("login-submit").click();
		await expect(page).toHaveURL(/\/infra\/jobs$/);
	});

	test("an external redirect-to falls back to the overview; other sign-in methods link to Frappe's page", async ({
		page,
	}) => {
		await mockLogin(page, ok);
		await page.goto("./login?redirect-to=https%3A%2F%2Fevil.example%2Finfra");
		await expect(page.getByTestId("login-alternatives")).toHaveAttribute(
			"href",
			"/login?redirect-to=https%3A%2F%2Fevil.example%2Finfra"
		);
		await fill(page);
		await page.getByTestId("login-submit").click();
		await expect(page).toHaveURL(/\/infra\/overview$/);
	});

	test("the background can be paused from the keyboard without stealing focus from the form", async ({
		page,
	}) => {
		await page.goto("./login");
		const toggle = page.getByTestId("scene-toggle");
		if (await toggle.isVisible()) {
			await toggle.focus();
			await page.keyboard.press("Enter");
			await expect(toggle).toHaveAttribute("aria-label", "Play background video");
		}
		await expect(page.getByTestId("scene-idle")).toHaveAttribute("tabindex", "-1");
	});
});

test("a signed-in session is sent from /login to the overview", async ({ browser }) => {
	const context = await browser.newContext();
	const page = await context.newPage();
	await injectBoot(page);
	await page.goto("/infra/login");
	await expect(page).toHaveURL(/\/infra\/overview$/);
	await context.close();
});
