import { expect, test } from "@playwright/test";

test.describe("design system components (B1.1)", () => {
	test.beforeEach(async ({ page }) => {
		await page.goto("./_design#components");
	});

	test("the components section renders every family", async ({ page }) => {
		const section = page.locator("#components");
		await expect(section).toBeVisible();
		await expect(section.getByTestId("buttons").getByRole("button")).toHaveCount(7);
		await expect(section.getByTestId("demo-table").locator("tbody tr")).toHaveCount(3);
		await expect(section.getByTestId("timeline").locator("li")).toHaveCount(4);
		await expect(section.getByTestId("terminal").locator(".xterm")).toBeVisible();
	});

	test("typed confirmation only unlocks with the exact target name", async ({ page }) => {
		await page.getByTestId("open-confirm").click();
		const dialog = page.getByRole("dialog");
		await expect(dialog).toBeVisible();
		const submit = dialog.getByTestId("confirm-submit");
		await expect(submit).toBeDisabled();
		await dialog.getByTestId("confirm-input").fill("SRV-0002");
		await expect(submit).toBeDisabled();
		await dialog.getByTestId("confirm-input").fill("SRV-0001");
		await expect(submit).toBeEnabled();
		await submit.click();
		await expect(page.getByTestId("confirmed")).toHaveText("confirmed: SRV-0001");
		await expect(dialog).toBeHidden();
	});

	test("toasts appear and can be dismissed", async ({ page }) => {
		// The sticky header can cover a freshly scrolled-to element; dispatch the click directly.
		await page.getByTestId("push-toast").dispatchEvent("click");
		const host = page.getByTestId("toast-host");
		await expect(host.getByRole("status")).toHaveCount(1);
		await host.getByRole("button", { name: "Dismiss" }).click();
		await expect(host.getByRole("status")).toHaveCount(0);
	});
});
