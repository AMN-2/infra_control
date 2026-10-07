import { expect, test } from "./fixtures";

// Against the Prism mock: the jobs list and the job viewer (B2.3).

test.describe("jobs (B2.3)", () => {
	test("the list opens a job; timeline, terminal and operator controls render", async ({
		page,
	}) => {
		await page.goto("./jobs");
		await expect(page.getByRole("row").nth(1)).toBeVisible();
		await page
			.getByRole("row", { name: /JOB-00042/ })
			.first()
			.click();
		await expect(page).toHaveURL(/\/infra\/jobs\/JOB-00042$/);
		await expect(page.getByTestId("job-badges")).toContainText("Running");
		const timeline = page.getByTestId("timeline");
		await expect(timeline.locator("li")).toHaveCount(5);
		// The running step is expanded and coloured; finished ones are collapsed.
		await expect(timeline.locator('li[data-status="Running"]')).toContainText(
			"Enable maintenance mode"
		);
		await expect(page.getByTestId("terminal")).toBeVisible();
		await expect(page.getByTestId("terminal")).toContainText("Backup saved");
		await expect(page.getByTestId("job-cancel")).toBeVisible();
		await page.getByTestId("job-cancel").click();
		await expect(page.getByTestId("confirm-submit")).toBeDisabled();
		await page.getByTestId("confirm-input").fill("JOB-00042");
		await expect(page.getByTestId("confirm-submit")).toBeEnabled();
	});
});
