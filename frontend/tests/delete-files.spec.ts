import { test, expect } from "@playwright/test";

test("generated file deletion requires confirmation and refreshes the file list", async ({ page }) => {
  let deleted = false;
  const file = { id: "output", name: "report.pdf", mime: "application/pdf", size: 12, kind: "artifact" };
  const task = () => ({ id: "deletion-test", goal: "Create a report", status: "completed", mode: "demo", created: 1, updated: 1, files: deleted ? [] : [file], turns: [], sources: [], current_file_ids: deleted ? [] : [file.id] });
  await page.route("**/api/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/auth/config") return route.fulfill({ json: { provider: "local" } });
    if (route.request().method() === "DELETE") {
      expect(path).toBe("/api/files/output");
      deleted = true;
      return route.fulfill({ json: { deleted: file.id } });
    }
    if (path.endsWith("/config")) return route.fulfill({ json: { mode: "demo", model: "Fixture planner", limits: { steps: 16, tokens: 30000, seconds: 600, cost: 1, upload_bytes: 10000000 } } });
    if (path.endsWith("/events")) return route.fulfill({ contentType: "text/event-stream", body: "" });
    return route.fulfill({ json: path.endsWith("/tasks") ? [task()] : task() });
  });
  await page.goto("/?task=deletion-test");
  await page.getByRole("tab", { name: /Files/ }).click();
  const remove = page.getByRole("button", { name: "Delete report.pdf" });
  page.once("dialog", (dialog) => dialog.dismiss());
  await remove.click();
  expect(deleted).toBe(false);
  await expect(remove).toBeVisible();
  page.once("dialog", (dialog) => dialog.accept());
  await remove.click();
  await expect(remove).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "No generated files yet" })).toBeVisible();
});
