import { expect, test } from "./fixtures";

// Against the Prism mock: Settings → GitHub (ADR 0005).

test.describe("github settings (ADR 0005)", () => {
	test("lists connections from the mock, verifies a token, and removes with typed confirmation", async ({
		page,
	}) => {
		await page.goto("./settings/github");
		await expect(page.getByTestId("git-connections")).toContainText("GH-SMARTCHOICE");
		await expect(page.getByTestId("git-GH-SMARTCHOICE")).toContainText("@smartchoice-iq");
		// Validation first, then the mock's verified connection comes back.
		await page.getByTestId("git-submit").click();
		await expect(page.getByTestId("git-connect")).toContainText("Required");
		await page.getByTestId("git-label").fill("gh-new");
		await page.getByTestId("git-token").fill("ghp_example");
		await page.getByTestId("git-submit").click();
		await expect(page.getByTestId("toast-host")).toContainText("GitHub connected");
		// The token field is cleared and never echoed anywhere on the page.
		await expect(page.getByTestId("git-token")).toHaveValue("");
		await expect(page.locator("body")).not.toContainText("ghp_example");
		await page.getByTestId("git-remove-GH-SMARTCHOICE").click();
		await expect(page.getByTestId("confirm-submit")).toBeDisabled();
		await page.getByTestId("confirm-input").fill("GH-SMARTCHOICE");
		await page.getByTestId("confirm-submit").click();
		await expect(page.getByTestId("git-GH-SMARTCHOICE")).toHaveCount(0);
	});

	test("the GitHub link is admin-only in the shell", async ({ page }) => {
		await page.goto("./overview");
		await expect(page.getByTestId("nav-github")).toBeVisible();
		await page.getByTestId("nav-github").click();
		await expect(page).toHaveURL(/\/infra\/settings\/github$/);
	});
});
