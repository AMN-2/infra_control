import { expect, test } from "./fixtures";

// Against the Prism mock: Security posture (A4.1) and the audit log.

test.describe("security and audit (A4.1)", () => {
	test("posture lists checks worst first and the 2FA switch asks for typed confirmation", async ({
		page,
	}) => {
		await page.goto("./settings/security");
		await expect(page.getByTestId("security-summary")).toContainText("fail");
		const checks = page.getByTestId("security-checks").locator("li");
		await expect(checks.first()).toHaveAttribute("data-status", "fail");
		await expect(page.getByTestId("check-2fa")).toContainText("Two-factor");
		await expect(page.getByTestId("tfa-state")).toHaveText(/disabled/i);
		await page.getByTestId("tfa-enable").click();
		await expect(page.getByTestId("confirm-submit")).toBeDisabled();
		await page.getByTestId("confirm-input").fill("ENABLE-2FA");
		await page.getByTestId("confirm-submit").click();
		await expect(page.getByTestId("toast-host")).toContainText(/Two-factor|Could not/);
	});

	test("audit log lists rows newest first with their targets and jobs", async ({ page }) => {
		await page.goto("./audit");
		const list = page.getByTestId("audit-list");
		await expect(list.locator("li")).toHaveCount(2);
		await expect(list.locator("li").first()).toContainText("jobs.run:site.migrate");
		await expect(
			list.locator("li").first().getByRole("link", { name: "JOB-00042" })
		).toBeVisible();
		await page.getByTestId("audit-action").fill("alerts");
		await expect(page.getByTestId("audit-list")).toBeVisible();
	});
});
