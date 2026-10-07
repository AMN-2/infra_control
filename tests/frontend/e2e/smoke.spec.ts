import { expect, test } from "@playwright/test";

test("the SPA boots under /infra", async ({ page }) => {
	const errors: string[] = [];
	page.on("pageerror", (e) => errors.push(e.message));
	await page.goto("./");
	await expect(page.getByTestId("app-title")).toBeVisible();
	expect(errors).toEqual([]);
});
