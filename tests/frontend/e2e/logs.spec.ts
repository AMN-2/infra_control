import { expect, test } from "./fixtures";

// Against the Prism mock: the Logs tab on a server starts a server.logs job (A3.8).

test.describe("log reader (A3.8)", () => {
	test("reads a log as a job and lists it under recent reads", async ({ page }) => {
		await page.goto("./servers/SRV-0002");
		await page.getByRole("tab", { name: /Logs/ }).click();
		await expect(page.getByTestId("log-reader")).toBeVisible();
		await page.getByTestId("log-source").selectOption("nginx_error");
		await page.getByTestId("log-lines").fill("50");
		await page.getByTestId("log-match").fill("error");
		await page.getByTestId("log-read").click();
		await expect(page.getByTestId("log-status")).toContainText("JOB-");
		await expect(page.getByTestId("log-terminal")).toBeVisible();
	});
});
