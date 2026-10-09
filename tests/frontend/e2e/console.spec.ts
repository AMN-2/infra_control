import { expect, test } from "./fixtures";

// Against the Prism mock: the Console tab (A3.9 command runner + ADR 0007 web console).
// The mock server is locked by a running job, so the runner must refuse to start a second
// one. The mock answers console.ticket but has no console service, so the terminal reports
// the failure instead of hanging; sessions and transcripts come from the contract examples.

test.describe("console tab", () => {
	test("command runner respects the one-job-per-server lock", async ({ page }) => {
		await page.goto("./servers/SRV-0002");
		await page.getByRole("tab", { name: /Console/ }).click();
		await expect(page.getByTestId("command-runner")).toBeVisible();
		await expect(page.getByTestId("cmd-run")).toBeDisabled();
		await page.getByTestId("cmd-command").fill("bench version");
		await expect(page.getByTestId("cmd-run")).toBeDisabled();
		await expect(page.getByTestId("cmd-run")).toHaveAttribute("title", /Wait for JOB-00042/);
		await expect(page.getByTestId("cmd-status")).toContainText("one at a time per server");
	});

	test("web console: ticket, failed bridge is reported, sessions replay a transcript", async ({
		page,
	}) => {
		await page.goto("./servers/SRV-0002");
		await page.getByRole("tab", { name: /Console/ }).click();
		await expect(page.getByTestId("ssh-terminal")).toBeVisible();
		await page.getByTestId("ssh-open").click();
		await expect(page.getByTestId("ssh-terminal")).toContainText(/failed/i, {
			timeout: 15000,
		});
		await expect(page.getByTestId("ssh-detail")).not.toHaveText("");
		const list = page.getByTestId("console-session-list");
		await expect(list.locator("li")).toHaveCount(2);
		await expect(list).toContainText("idle timeout");
		await page.getByTestId("session-20261009-081500-a1b2c3").click();
		await expect(page.getByTestId("console-transcript-label")).toContainText(
			"20261009-081500-a1b2c3"
		);
		await expect(page.getByTestId("console-transcript")).toContainText("bench version");
	});
});
