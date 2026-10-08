import { expect, test } from "./fixtures";

// Against the Prism mock: the New server wizard (ADR 0006).

test.describe("provision wizard (ADR 0006)", () => {
	test("plans come from the catalogue, the region filters them, and the job is created", async ({
		page,
	}) => {
		await page.goto("./servers");
		await page.getByTestId("server-new").click();
		const dialog = page.getByTestId("provision-dialog");
		await expect(dialog).toBeVisible();
		await expect(page.getByTestId("prov-plans").locator("button")).toHaveCount(3);
		await expect(page.getByTestId("prov-plan-s-2vcpu-4gb")).toHaveAttribute(
			"aria-pressed",
			"true"
		);
		await expect(page.getByTestId("prov-plan-s-2vcpu-4gb")).toContainText("2 vCPU · 4 GB RAM");
		await page.getByTestId("prov-family-general").click();
		await expect(page.getByTestId("prov-plans").locator("button")).toHaveCount(1);
		await page.getByTestId("prov-plan-g-2vcpu-8gb").click();
		// London does not offer the general plan: the wizard says so instead of sending it.
		await page.getByTestId("prov-region").selectOption("lon1");
		await page.getByTestId("prov-hostname").fill("app-03.fra1");
		await page.getByTestId("prov-submit").click();
		await expect(dialog).toContainText("not offered in the chosen region");
		await page.getByTestId("prov-region").selectOption("fra1");
		await expect(page.getByTestId("prov-summary")).toContainText("$63/month");
		await page.getByTestId("prov-submit").click();
		await expect(page).toHaveURL(/\/infra\/jobs\/JOB-/);
	});
});
