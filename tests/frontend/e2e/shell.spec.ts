import { expect, test } from "./fixtures";

test.describe("app shell (B1.2)", () => {
	test("navigation, titles and the realtime indicator", async ({ page }) => {
		await page.goto("./");
		await expect(page).toHaveURL(/\/infra\/overview$/);
		await expect(page.getByTestId("app-shell")).toBeVisible();
		await expect(page).toHaveTitle("Overview · Infra Control");
		await page.getByTestId("nav-jobs").click();
		await expect(page).toHaveURL(/\/infra\/jobs$/);
		await expect(page.getByTestId("nav-jobs")).toHaveAttribute("aria-current", "page");
		await expect(page.getByTestId("realtime-indicator")).toBeVisible();
		await page.goto("./no/such/page");
		await expect(page.getByText("Nothing lives at this address")).toBeVisible();
	});

	test("command palette opens with Ctrl+K and navigates", async ({ page }) => {
		await page.goto("./overview");
		await page.keyboard.press("Control+k");
		const palette = page.getByTestId("command-palette");
		await expect(palette).toBeVisible();
		await palette.getByRole("combobox").fill("alert");
		await expect(palette.getByRole("option")).toHaveCount(1);
		await page.keyboard.press("Enter");
		await expect(page).toHaveURL(/\/infra\/alerts$/);
		await expect(palette).toBeHidden();
	});

	test("the showcase is reachable for the dev admin session", async ({ page }) => {
		await page.goto("./_design");
		await expect(page.getByTestId("design-showcase")).toBeVisible();
	});
});
