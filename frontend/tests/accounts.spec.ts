import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("sign in, restore saved work after reload, refresh the session, and sign out", async ({
  page,
}) => {
  const user = {
    id: "00000000-0000-4000-8000-000000000001",
    email: "reader@example.test",
    aud: "authenticated",
    role: "authenticated",
    app_metadata: {},
    user_metadata: {},
    created_at: new Date().toISOString(),
  };
  const token = "test-account-token";
  let refreshes = 0;
  await page.route("https://accounttest.supabase.co/**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith("/logout")) return route.fulfill({ json: {} });
    if (url.pathname.endsWith("/token")) {
      if (url.searchParams.get("grant_type") === "refresh_token") refreshes++;
      return route.fulfill({
        json: {
          access_token: token,
          refresh_token: "test-refresh-token",
          token_type: "bearer",
          expires_in: 3600,
          user,
        },
      });
    }
    return route.fulfill({ json: { user } });
  });
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/auth/config")
      return route.fulfill({
        json: {
          provider: "supabase",
          url: "https://accounttest.supabase.co",
          publishableKey: "sb_publishable_test",
        },
      });
    expect(route.request().headers().authorization).toBe(`Bearer ${token}`);
    if (path === "/api/tasks")
      return route.fulfill({
        json: [
          {
            id: "saved-account-task",
            goal: "My saved account research",
            status: "completed",
            mode: "demo",
            created: 1,
            updated: 1,
            artifact_count: 0,
          },
        ],
      });
    if (path === "/api/config")
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
    return route.fulfill({ json: {} });
  });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Pick up where you left off." }),
  ).toBeVisible();
  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(accessibility.violations).toEqual([]);
  await page.screenshot({ path: `../evaluation/account-${test.info().project.name}.png`, fullPage: true });
  await page.getByLabel("Email address").fill(user.email);
  await page
    .getByLabel("Password", { exact: true })
    .fill("Only-a-mocked-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Pick up where you left off." }),
  ).not.toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Pick up where you left off." }),
  ).not.toBeVisible();
  // Expire the persisted test session: the SDK must renew it before API access.
  await page.evaluate(() => {
    const key = "sb-accounttest-auth-token";
    const session = JSON.parse(localStorage.getItem(key)!);
    session.expires_at = 1;
    localStorage.setItem(key, JSON.stringify(session));
  });
  await page.reload();
  await expect.poll(() => refreshes).toBeGreaterThan(0);
  const menu = page.getByRole("button", { name: "Open navigation" });
  if (await menu.isVisible()) await menu.click();
  await expect(
    page.getByText("My saved account research", { exact: true }).first(),
  ).toBeVisible();
  await page
    .getByRole("button", { name: /settings/i })
    .first()
    .click();
  await expect(page.getByText(user.email, { exact: true })).toBeVisible();
  await expect(page.getByLabel("Live access token")).toHaveCount(0);
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Pick up where you left off." }),
  ).toBeVisible();
  await expect(
    page.getByText("My saved account research", { exact: true }),
  ).toHaveCount(0);
});

test("signup confirmation and password reset show actionable feedback", async ({
  page,
}) => {
  await page.route("**/api/auth/config", (route) =>
    route.fulfill({
      json: {
        provider: "supabase",
        url: "https://accounttest.supabase.co",
        publishableKey: "sb_publishable_test",
      },
    }),
  );
  await page.route("https://accounttest.supabase.co/**", (route) =>
    route.fulfill({ json: { user: { id: "test" }, session: null } }),
  );
  await page.goto("/");
  await page
    .getByRole("button", { name: "New here? Create an account" })
    .click();
  await page.getByLabel("Email address").fill("reader@example.test");
  await page
    .getByLabel("Password", { exact: false })
    .fill("Only-a-mocked-password");
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(page.getByRole("status")).toContainText("Check your email");
  await page.getByRole("button", { name: "Back to sign in" }).click();
  await page.getByRole("button", { name: "Forgot password?" }).click();
  await page.getByRole("button", { name: "Send reset link" }).click();
  await expect(page.getByRole("status")).toContainText(
    "If this address has an account",
  );
});
