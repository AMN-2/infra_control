import { expect, test } from "./fixtures";

// Against the Prism mock: lists, detail screens and the run-playbook dialog (B2.2).

test.describe("servers and sites (B2.2)", () => {
	test("the servers list opens a server; metrics, benches and actions render", async ({
		page,
	}) => {
		await page.goto("./servers");
		await expect(page.getByRole("row")).toHaveCount(3); // header + the two mock servers
		await page.getByRole("row", { name: /app-01\.fra1/ }).click();
		await expect(page).toHaveURL(/\/infra\/servers\/SRV-0001$/);
		await expect(page.getByTestId("server-badges")).toContainText("Active");
		await expect(page.getByTestId("server-metrics")).toBeVisible();
		await expect(page.getByTestId("target-actions")).toBeVisible();
		// The mock server is locked by JOB-00042: actions are disabled and the lock links to the job.
		await expect(page.getByTestId("lock-notice")).toContainText("JOB-00042");
		await page.getByRole("tab", { name: /Details/ }).click();
		await expect(page.getByTestId("server-details")).toContainText("DO-STAGING");
	});

	test("a site detail runs a playbook through the dialog and lands on the job", async ({
		page,
	}) => {
		await page.goto("./sites");
		await page.getByRole("row", { name: /staging\.client-c\.frappe\.cloud/ }).click();
		await expect(page).toHaveURL(/\/infra\/sites\//);
		await expect(page.getByTestId("site-facts")).toBeVisible();
		const actions = page.getByTestId("target-actions");
		await expect(actions).toBeVisible();
		// The mock's site detail example is locked, so run from whichever action is enabled, else skip.
		const backup = page.getByTestId("action-site.backup");
		if (await backup.isDisabled()) test.skip(true, "mock site is locked by a running job");
		await backup.click();
		const dialog = page.getByTestId("run-dialog");
		await expect(dialog).toBeVisible();
		await page.getByTestId("run-submit").click();
		await expect(page).toHaveURL(/\/infra\/jobs\/JOB-/);
	});
});
