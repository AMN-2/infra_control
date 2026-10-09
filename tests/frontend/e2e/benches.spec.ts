import { expect, test } from "./fixtures";

// ADR 0009: benches with apps, versions and upstream state, against the Prism mock.
test.describe("benches", () => {
	test("list: tiles, apps with update state, filter by state, open a bench", async ({
		page,
	}) => {
		await page.goto("./benches");
		await expect(page).toHaveTitle("Benches · Infra Control");
		await expect(page.getByTestId("bench-row")).toHaveCount(2);
		await expect(
			page.getByTestId("bench-tile-update_available").getByTestId("stat-value")
		).toHaveText("2");
		await page.getByTestId("bench-tile-up_to_date").click();
		await expect(page).toHaveURL(/updates=up_to_date/);
		await expect(page.getByTestId("bench-row")).toHaveCount(0);
		await page.getByTestId("bench-tile-up_to_date").click();
		await page.getByTestId("bench-row").first().click();
		await expect(page).toHaveURL(/\/infra\/benches\/BENCH-/);
	});

	test("detail: apps table with upstream state, check for updates, version switch dialog", async ({
		page,
	}) => {
		await page.goto("./benches/BENCH-FC-01");
		await expect(page.getByTestId("bench-facts")).toBeVisible();
		await expect(page.getByTestId("bench-badges")).toContainText("behind upstream");
		const apps = page.getByTestId("bench-apps");
		await expect(apps).toBeVisible();
		await expect(page.getByTestId("app-state-frappe")).toContainText("12 commit(s) behind");
		await expect(apps).toContainText("latest v15.101.0");
		await page.getByTestId("bench-check-updates").click();
		await expect(page.getByText(/app\(s\) have updates|Every app is current/)).toBeVisible();
		await page.getByTestId("app-switch-frappe").click();
		const dialog = page.getByTestId("switch-version");
		await expect(dialog).toBeVisible();
		await expect(dialog).toContainText("latest v15.101.0");
		await dialog.getByRole("button", { name: "Cancel" }).click();
		await expect(dialog).toBeHidden();
		await page.getByRole("tab", { name: /Sites/ }).click();
		await expect(page.getByTestId("bench-site-row").first()).toBeVisible();
	});

	test("a server's bench row opens the bench screen", async ({ page }) => {
		await page.goto("./servers/SRV-0001");
		await page.getByRole("tab", { name: /Benches/ }).click();
		const row = page.locator("tr", { has: page.getByTestId("bench-new-site-BENCH-0001") });
		await row.locator("td").first().click();
		await expect(page).toHaveURL(/\/infra\/benches\/BENCH-0001$/);
	});
});
