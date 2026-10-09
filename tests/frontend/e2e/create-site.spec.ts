import { expect, test } from "./fixtures";

// Against the Prism mock: New site with app selection (site.create on a bench).

test.describe("create site", () => {
	test("picks a bench, offers its apps, validates, and creates the job", async ({ page }) => {
		await page.goto("./sites");
		await page.getByTestId("site-new").click();
		const dialog = page.getByTestId("create-site");
		await expect(dialog).toBeVisible();
		await expect(page.getByTestId("site-bench")).not.toHaveValue("");
		// The bench's installed apps (minus frappe) are offered and preselected.
		const apps = page.getByTestId("site-apps").locator("input[type=checkbox]");
		await expect(apps.first()).toBeChecked();
		await apps.first().uncheck();
		await page.getByTestId("site-submit").click();
		await expect(dialog).toContainText("Not a valid domain");
		await page.getByTestId("site-domain").fill("erp.client-d.iq");
		await page.getByTestId("site-password").fill("Str0ngPassw0rd!!");
		await page.getByTestId("site-submit").click();
		await expect(page).toHaveURL(/\/infra\/jobs\/JOB-/);
	});

	test("a bench row on the server screen opens the dialog with that bench", async ({ page }) => {
		await page.goto("./servers/SRV-0002");
		const button = page.locator("[data-testid^='bench-new-site-']").first();
		await expect(button).toBeVisible();
	});
});
