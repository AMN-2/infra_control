import { expect, test } from "./fixtures";

// Against the Prism mock: the Console tab (A3.9). The mock server is locked by a running job,
// so the runner must refuse to start a second one and say which job holds the server.

test.describe("command runner (A3.9)", () => {
	test("renders the runner and respects the one-job-per-server lock", async ({ page }) => {
		await page.goto("./servers/SRV-0002");
		await page.getByRole("tab", { name: /Console/ }).click();
		await expect(page.getByTestId("command-runner")).toBeVisible();
		await expect(page.getByTestId("cmd-run")).toBeDisabled();
		await page.getByTestId("cmd-command").fill("bench version");
		await expect(page.getByTestId("cmd-run")).toBeDisabled();
		await expect(page.getByTestId("cmd-run")).toHaveAttribute("title", /Wait for JOB-00042/);
		await expect(page.getByTestId("cmd-status")).toContainText("one at a time per server");
		await expect(page.getByTestId("cmd-terminal")).toBeVisible();
	});
});
