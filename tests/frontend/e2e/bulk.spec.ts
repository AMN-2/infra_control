import { expect, test } from "./fixtures";

// ADR 0009: the rollout wizard picks targets from the inventory and runs the preflight.
test.describe("bulk rollouts", () => {
	test("wizard: operation, tick targets, run checks, drop blocked, start", async ({ page }) => {
		await page.goto("./bulk");
		await expect(page.getByTestId("bulk-tiles")).toBeVisible();
		await expect(page.getByTestId("bulk-row").first()).toBeVisible();
		await page.getByTestId("bulk-new").click();
		const start = page.getByTestId("bulk-start");
		await expect(start).toBeDisabled();
		await page.locator("#bulk-playbook").selectOption("site.migrate");
		await expect(page.getByTestId("bulk-targets-step")).toBeVisible();
		await expect(page.getByTestId("bulk-candidate").first()).toBeVisible();
		await page.getByTestId("bulk-pick-all").click();
		const picked = await page.getByTestId("bulk-candidate").count();
		expect(picked).toBeGreaterThan(1);
		await expect(page.getByTestId("bulk-preflight-step")).toBeVisible();
		await expect(start).toBeDisabled();
		await page.getByTestId("bulk-run-checks").click();
		const table = page.getByTestId("bulk-preflight");
		await expect(table).toBeVisible();
		// The mock answers with one ready and one blocked target.
		await expect(page.getByTestId("bulk-drop-failing")).toBeVisible();
		await page.getByTestId("bulk-drop-failing").click();
		await expect(page.getByTestId("bulk-drop-failing")).toHaveCount(0);
		await expect(page.getByTestId("bulk-plan-step")).toBeVisible();
		await expect(start).toBeEnabled();
		await start.click();
		await expect(page.getByTestId("bulk-detail")).toBeVisible();
		await expect(page.getByTestId("bulk-targets")).toContainText("Canary");
	});

	test("changing the selection invalidates the checks", async ({ page }) => {
		await page.goto("./bulk");
		await page.getByTestId("bulk-new").click();
		await page.locator("#bulk-playbook").selectOption("site.migrate");
		await page.getByTestId("bulk-candidate").first().check();
		await page.getByTestId("bulk-run-checks").click();
		await expect(page.getByTestId("bulk-preflight")).toBeVisible();
		await page.getByTestId("bulk-candidate").nth(1).check();
		await expect(page.getByText("Selection changed: run the checks again.")).toBeVisible();
		await expect(page.getByTestId("bulk-start")).toBeDisabled();
	});
});
