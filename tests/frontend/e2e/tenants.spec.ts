import { expect, test } from "./fixtures";

// Against the Prism mock: tenants list, detail with sites, attach and suspend flows.

test.describe("tenants", () => {
	test("lists tenants, opens one, attaches a site and suspends all with typed confirmation", async ({
		page,
	}) => {
		await page.goto("./tenants");
		const table = page.getByTestId("tenants-table");
		await expect(table).toContainText("Client D Trading");
		await expect(table).toContainText("suspended");
		await page.getByRole("row", { name: /CLIENT-D/ }).click();
		await expect(page).toHaveURL(/\/infra\/tenants\/CLIENT-D$/);
		await expect(page.getByTestId("tenant-sites")).toContainText("erp.client-d.iq");
		await expect(page.getByTestId("tenant-form-title")).toHaveValue("Client D Trading");
		await page.getByTestId("tenant-suspend").click();
		await expect(page.getByTestId("confirm-submit")).toBeDisabled();
		await page.getByTestId("confirm-input").fill("CLIENT-D");
		await page.getByTestId("confirm-submit").click();
		await expect(page.getByTestId("toast-host")).toContainText("Suspending sites");
	});

	test("creates a tenant from the list", async ({ page }) => {
		await page.goto("./tenants");
		await page.getByTestId("tenant-new").click();
		await page.getByTestId("tenant-submit").click();
		await expect(page.getByTestId("tenant-create")).toContainText("Required");
		await page.getByTestId("tenant-label").fill("client-f");
		await page.getByTestId("tenant-title").fill("Client F");
		await page.getByTestId("tenant-submit").click();
		await expect(page).toHaveURL(/\/infra\/tenants\//);
	});
});
