import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("follow-up stays in the saved conversation and preserves earlier reports", async ({
  page,
}) => {
  const original = {
    id: "old-report",
    name: "report.md",
    mime: "text/markdown",
    size: 40,
    kind: "artifact",
  };
  const revised = { ...original, id: "new-report" };
  let continued = false;
  const task = () => ({
    id: "conversation-test",
    goal: "Analyze the sales document",
    status: "completed",
    mode: "demo",
    created: 1,
    updated: 2,
    files: continued ? [original, revised] : [original],
    sources: [],
    current_goal: continued
      ? "Show more detail using the same document"
      : "Analyze the sales document",
    current_file_ids: continued ? [revised.id] : null,
    turns: continued
      ? [
          {
            goal: "Analyze the sales document",
            status: "completed",
            summary: "First report ready",
            file_ids: [original.id],
            created: 1,
          },
        ]
      : [],
  });
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/auth/config") return route.fulfill({ json: { provider: "local" } });
    if (path.endsWith("/messages")) {
      expect(route.request().postDataJSON().goal).toBe(
        "Show more detail using the same document",
      );
      continued = true;
      return route.fulfill({ json: { status: "queued" } });
    }
    if (path.endsWith("/events"))
      return route.fulfill({ contentType: "text/event-stream", body: "" });
    if (path.includes("/files/"))
      return route.fulfill({
        contentType: "text/markdown",
        body: path.endsWith("new-report")
          ? "# Revised analysis\nMore detail from the same document."
          : "# Original analysis\nThe first report is preserved.",
      });
    if (path.endsWith("/config"))
      return route.fulfill({
        json: {
          mode: "demo",
          model: "Fixture planner",
          search_configured: true,
          limits: {
            steps: 16,
            tokens: 30000,
            seconds: 600,
            cost: 1,
            upload_bytes: 10000000,
          },
        },
      });
    return route.fulfill({ json: path.endsWith("/tasks") ? [task()] : task() });
  });
  await page.goto("/?task=conversation-test");
  await expect(
    page.getByRole("heading", { name: "Original analysis" }),
  ).toBeVisible();
  await page
    .getByLabel("Continue this conversation")
    .fill("Show more detail using the same document");
  await page.getByRole("button", { name: "Send follow-up" }).click();
  await expect(
    page.getByRole("heading", { name: "Revised analysis" }),
  ).toBeVisible();
  await expect(page).toHaveURL(/task=conversation-test/);
  await page.locator(".previous-response summary").click();
  await expect(
    page.getByRole("heading", { name: "Original analysis" }),
  ).toBeVisible();
  await page.reload();
  await expect(page.locator(".conversation-message")).toHaveCount(2);
  await expect(
    page.getByRole("heading", { name: "Revised analysis" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  const accessibility = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(accessibility.violations).toEqual([]);
  await page.screenshot({
    path: `../evaluation/conversation-${test.info().project.name}.png`,
    fullPage: true,
  });
});
