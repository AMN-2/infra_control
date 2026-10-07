import { expect, injectBoot, test } from "./fixtures";

test.describe("design showcase", () => {
	test("renders every section without errors", async ({ page }) => {
		const errors: string[] = [];
		page.on("pageerror", (e) => errors.push(e.message));
		page.on("console", (m) => {
			if (m.type() === "error") errors.push(m.text());
		});
		await page.goto("./_design");
		for (const id of ["moments", "surfaces", "color", "status", "type", "space", "motion"]) {
			await expect(page.locator(`section#${id}`)).toBeVisible();
		}
		expect(errors).toEqual([]);
	});

	test("overview numbers land on their final values", async ({ page }) => {
		await page.goto("./_design");
		await expect(page.locator("#moments").getByTestId("stat-value")).toHaveText([
			"18",
			"142",
			"3",
			"1",
		]);
	});

	test("reduced motion applies instantly and is reflected on <html>", async ({ page }) => {
		await page.goto("./_design");
		await page.getByTestId("motion-mode").getByRole("radio", { name: "Reduced" }).click();
		await expect(page.locator("html")).toHaveAttribute("data-motion", "reduce");
		const dur = await page.evaluate(() =>
			getComputedStyle(document.documentElement).getPropertyValue("--ic-dur-base").trim()
		);
		expect(parseFloat(dur)).toBe(0);
		await page.getByTestId("replay-overview").click();
		await expect(page.getByTestId("stat-value").first()).toHaveText("18", { timeout: 100 });
	});

	test("honours the OS reduced-motion preference", async ({ browser }) => {
		const context = await browser.newContext({ reducedMotion: "reduce" });
		const page = await context.newPage();
		await injectBoot(page);
		await page.goto("./_design");
		const dur = await page.evaluate(() =>
			getComputedStyle(document.documentElement).getPropertyValue("--ic-dur-scene").trim()
		);
		expect(parseFloat(dur)).toBe(0);
		await context.close();
	});

	test("a fired alert enters at the top of the list", async ({ page }) => {
		await page.goto("./_design");
		const items = page.getByTestId("alert-list").locator("li");
		await expect(items).toHaveCount(2);
		await page.getByTestId("fire-alert").click();
		await expect(items).toHaveCount(3);
		await expect(items.first()).toContainText("Queue backlog above 500");
	});

	test("running-job glow follows job state", async ({ page }) => {
		await page.goto("./_design");
		const server = page.getByTestId("node-srv");
		await expect(server).toHaveClass(/ic-glow/);
		await page.getByTestId("toggle-job").click();
		await expect(server).not.toHaveClass(/ic-glow/);
	});
});
