import { expect, test } from "./fixtures";

// Runs against the Prism mock (contracts/mock) through the Vite proxy; see playwright.config.

test.describe("overview (B2.1)", () => {
	test("headline numbers, running jobs and recent alerts come from overview.summary", async ({
		page,
	}) => {
		await page.goto("./overview");
		const stats = page.getByTestId("overview-stats");
		await expect(stats).toBeVisible();
		await expect(stats.getByTestId("stat-value")).toHaveCount(4);
		// The count-up settles on the mock's totals (3 servers, 5 sites).
		await expect(page.getByTestId("stat-servers").getByTestId("stat-value")).toHaveText("3");
		await expect(page.getByTestId("stat-sites").getByTestId("stat-value")).toHaveText("5");
		await expect(page.getByTestId("running-jobs")).toContainText("Migrate site");
		await expect(page.getByTestId("recent-alerts")).toContainText("Disk usage");
		await page.getByTestId("stat-jobs").click();
		await expect(page).toHaveURL(/\/infra\/jobs$/);
	});
});

test.describe("topology (B2.1)", () => {
	test("renders every node in its column and opens a server on click", async ({ page }) => {
		await page.goto("./topology");
		const graph = page.getByTestId("topology-graph");
		await expect(graph).toBeVisible();
		await expect(graph.locator("[data-type='provider']")).toHaveCount(2);
		await expect(graph.locator("[data-type='server']")).toHaveCount(2);
		await expect(graph.locator("[data-type='site']")).toHaveCount(4);
		// The running job glows on its server node.
		await expect(page.getByTestId("topology-node-server:SRV-0001")).toHaveClass(/ic-glow/);
		await page.getByTestId("topology-fit").click();
		await page.getByTestId("topology-node-server:SRV-0002").click();
		await expect(page).toHaveURL(/\/infra\/servers\/SRV-0002$/);
	});
});
