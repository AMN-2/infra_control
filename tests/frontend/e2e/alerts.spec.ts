import { expect, test } from "./fixtures";

// Against the Prism mock: the alerts screen and the rule editor (B3.2).

test.describe("alerts (B3.2)", () => {
	test("lists alerts firing first, acknowledges in place, and filters", async ({ page }) => {
		await page.goto("./alerts");
		const list = page.getByTestId("alerts-list");
		await expect(list.locator("li")).toHaveCount(2);
		await expect(list.locator("li").first()).toHaveAttribute("data-status", "firing");
		await expect(list.locator("li").first()).toContainText("No heartbeat from SRV-0002");
		await expect(page.getByTestId("alerts-firing-count")).toHaveText("1 firing");
		// The target links to its detail screen.
		await expect(
			list.locator("li").first().getByRole("link", { name: "SRV-0002" })
		).toHaveAttribute("href", /\/infra\/servers\/SRV-0002$/);
		// Acknowledge flips the badge optimistically; the mock then returns the acknowledged row.
		await page.getByTestId("ack-ALERT-00018").click();
		await expect(page.getByTestId("alert-ALERT-00018")).toHaveAttribute(
			"data-status",
			"acknowledged"
		);
		await expect(page.getByTestId("ack-ALERT-00018")).toHaveCount(0);
		// Changing a filter refetches with the query.
		const request = page.waitForRequest(
			(r) => r.url().includes("alerts.list") && r.url().includes("severity=critical")
		);
		await page.getByTestId("alerts-severity").selectOption("critical");
		await request;
	});

	test("rules tab: built-in rules expose only their tunable, metric rules can be created and deleted", async ({
		page,
	}) => {
		await page.goto("./alerts");
		await page.getByRole("tab", { name: /Rules/ }).click();
		const rules = page.getByTestId("rules-list");
		await expect(rules.locator("li").first()).toContainText("Server heartbeat missing");
		await expect(page.getByTestId("rule-RULE-0001")).toContainText("built-in");
		await expect(page.getByTestId("rule-delete-RULE-0001")).toHaveCount(0);
		await expect(page.getByTestId("rule-delete-RULE-0002")).toBeVisible();

		// Editing the heartbeat rule shows minutes only; no metric/operator/threshold.
		await page.getByTestId("rule-edit-RULE-0001").click();
		const form = page.getByTestId("rule-form");
		await expect(form).toBeVisible();
		await expect(page.getByTestId("rule-for-minutes")).toHaveValue("3");
		await expect(page.getByTestId("rule-threshold")).toHaveCount(0);
		await expect(form.locator("#rule-metric")).toHaveCount(0);
		await page.getByRole("button", { name: "Cancel" }).click();
		await expect(form).toBeHidden();

		// Creating a metric rule: validation blocks an empty title, then the mock returns the rule.
		await page.getByTestId("rule-new").click();
		await expect(page.getByTestId("rule-form")).toBeVisible();
		await page.getByTestId("rule-submit").click();
		await expect(page.getByTestId("rule-form")).toContainText("Title is required.");
		await page.getByTestId("rule-title").fill("RAM above 80%");
		await page.getByTestId("rule-threshold").fill("80");
		await page.getByTestId("rule-submit").click();
		await expect(page.getByTestId("rule-form")).toBeHidden();
		await expect(page.getByTestId("toast-host")).toContainText("Rule created");

		// Delete needs the typed rule name.
		await page.getByTestId("rule-delete-RULE-0002").click();
		await expect(page.getByTestId("confirm-submit")).toBeDisabled();
		await page.getByTestId("confirm-input").fill("RULE-0002");
		await page.getByTestId("confirm-submit").click();
		await expect(page.getByTestId("rule-RULE-0002")).toHaveCount(0);
	});
});
