import { expect, test } from "./fixtures";

// Against the Prism mock: the backup schedule card on a site and the backup picker (A4.2).

test.describe("backups (A4.2)", () => {
	test("shows the policy from the mock and saves a change", async ({ page }) => {
		await page.goto("./sites");
		await page.getByRole("row", { name: /demo\.smartchoice-iq\.com/ }).click();
		await expect(page.getByTestId("backup-policy")).toBeVisible();
		await expect(page.getByTestId("policy-frequency")).toHaveValue("daily");
		await expect(page.getByTestId("policy-retain")).toHaveValue("14");
		await expect(page.getByTestId("policy-save")).toBeDisabled();
		await page.getByTestId("policy-frequency").selectOption("weekly");
		await expect(page.getByTestId("policy-save")).toBeEnabled();
		await page.getByTestId("policy-save").click();
		await expect(page.getByTestId("toast-host")).toContainText("Backup schedule saved");
	});
});
