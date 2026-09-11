import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("missing saved task returns to workspace with an actionable error", async ({
  page,
}) => {
  await page.goto("/?task=missing-task");
  await expect(page.locator(".error-notice")).toContainText(
    "This task is unavailable",
  );
  await expect(page.getByLabel("Your goal")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Show workspace information" }),
  ).toContainText("Demo mode");
});

test("sample analysis renders report, downloads files, and survives reload", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Show workspace information" }),
  ).toContainText("Demo mode");
  await page.getByRole("button", { name: "Load example" }).click();
  await expect(page.locator(".upload-chips")).toContainText("sales.csv");
  await expect(page.getByLabel("Your goal")).toHaveValue(/three weakest/);
  await page.getByLabel("Your goal").press("Control+Enter");
  await expect(page.locator(".task-heading .task-status")).toHaveText(
    "Completed",
    { timeout: 60000 },
  );
  await expect(page.locator(".markdown")).toContainText("Beauty (10,000.00)");
  await expect(page.locator(".generated-chart")).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Download report.pdf", exact: true })
    .click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("report.pdf");
  expect(await download.failure()).toBeNull();
  const savedUrl = page.url();
  await page.reload();
  await expect(page.locator(".task-heading .task-status")).toHaveText(
    "Completed",
  );
  await expect(page.locator(".markdown")).toContainText("Beauty (10,000.00)");
  expect(page.url()).toBe(savedUrl);
  const reportAccessibility = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(reportAccessibility.violations).toEqual([]);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: `test-results/report-${test.info().project.name}.png`,
    fullPage: true,
  });
  await page.getByRole("tab", { name: /Files/ }).click();
  await page
    .locator(".file-card-open")
    .filter({ hasText: "report.md" })
    .click();
  await expect(
    page.getByRole("region", { name: "Preview report.md" }),
  ).toBeVisible();
  await expect(page.locator(".file-viewer .markdown")).toContainText("Beauty");
  await page.getByRole("button", { name: "Close preview" }).click();
  await page.getByRole("tab", { name: /Sources/ }).click();
  await expect(page.getByText("Demo fixture", { exact: true })).toBeVisible();
  await page.getByRole("tab", { name: /Activity/ }).click();
  await expect(page.locator(".execution-log")).toContainText(
    "Analyze categories",
  );
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  expect(errors).toEqual([]);
});

test("workspace templates, settings keyboard, and history search work", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Run task", exact: true }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Research a topic" }).click();
  await expect(page.getByLabel("Your goal")).toHaveValue(
    /Research recent trends/,
  );
  await page
    .getByRole("button", { name: "Show workspace information" })
    .click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByLabel("Live access token")).toBeVisible();
  const settingsAccessibility = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(settingsAccessibility.violations).toEqual([]);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await expect(
    page.getByRole("button", { name: "Show workspace information" }),
  ).toBeFocused();
  await page.getByLabel("Your goal").fill("");
  const homeAccessibility = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(homeAccessibility.violations).toEqual([]);
  await page.screenshot({
    path: `test-results/workspace-${test.info().project.name}.png`,
    fullPage: true,
  });
  if (test.info().project.name === "mobile")
    await page.getByRole("button", { name: "Open navigation" }).click();
  await page
    .getByRole("navigation", { name: "Workspace navigation" })
    .getByRole("button", { name: /All tasks/ })
    .click();
  await page.getByLabel("Search task history").fill("no-such-task-zzzz");
  await expect(
    page.getByRole("heading", { name: "No matching tasks" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Clear search" }).click();
  await expect(page.locator(".task-row").first()).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});

test("unauthorized service shows a sign-in state without demo claims", async ({
  page,
}) => {
  await page.route("**/api/config", (route) =>
    route.fulfill({
      status: 401,
      json: { detail: "Valid access token required" },
    }),
  );
  await page.route("**/api/tasks", (route) =>
    route.fulfill({
      status: 401,
      json: { detail: "Valid access token required" },
    }),
  );
  await page.goto("/");
  await expect(page.locator(".connection-notice")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Show workspace information" }),
  ).not.toContainText("Demo mode");
  await expect(page.locator(".connection-notice")).toContainText(
    /token|sign in/i,
  );
});
