import { expect, test } from "./fixtures";

test("the SPA boots under /infra", async ({ page }) => {
	const errors: string[] = [];
	page.on("pageerror", (e) => errors.push(e.message));
	await page.goto("./");
	await expect(page.getByTestId("app-shell")).toBeVisible();
	expect(errors).toEqual([]);
});
