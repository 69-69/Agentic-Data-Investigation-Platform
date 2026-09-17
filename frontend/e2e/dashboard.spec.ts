import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import fixture from "../tests/fixtures/investigation.json" with { type: "json" };
test("happy path: results, citations, SQL, activity and session history", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.route("**/api/experience/investigations**", async (route) => {
    await route.fulfill({
      json:
        route.request().method() === "POST"
          ? {
              investigationId: fixture.investigationId,
              question: fixture.question,
              status: fixture.status,
              createdAt: fixture.createdAt,
            }
          : fixture,
    });
  });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Turn questions into evidence." }),
  ).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page
    .getByRole("button", { name: "Volume decline", exact: true })
    .click();
  await page.getByRole("button", { name: "Run investigation" }).click();
  await expect(
    page.getByRole("heading", { name: fixture.question }),
  ).toBeVisible();
  await page.getByRole("button", { name: "View evidence e1" }).click();
  await expect(
    page.getByRole("region", { name: "Evidence e1 rows" }),
  ).toContainText("1400");
  await page.getByRole("tab", { name: /SQL/ }).click();
  await page.locator("summary").first().click();
  await expect(page.getByLabel("SQL query s1", { exact: true })).toContainText(
    "SELECT",
  );
  await page.getByRole("tab", { name: /Activity/ }).click();
  await expect(
    page.getByRole("region", { name: "Tool execution timeline" }),
  ).toContainText("Execute guarded SQL");
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.reload();
  await page
    .getByRole("navigation", { name: "Investigation history" })
    .getByRole("button")
    .first()
    .click();
  await expect(
    page.getByRole("heading", { name: fixture.question }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect(errors).toEqual([]);
});
test("connection failure is actionable and never fabricates a result", async ({
  page,
}) => {
  await page.route("**/api/experience/investigations", (route) =>
    route.fulfill({
      status: 503,
      json: { error: { code: "AGENT_UNAVAILABLE", message: "private detail" } },
    }),
  );
  await page.goto("/");
  await page
    .getByRole("button", { name: "Volume decline", exact: true })
    .click();
  await page.getByRole("button", { name: "Run investigation" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Check that Java and Python are running",
  );
  await expect(page.getByText("private detail")).toHaveCount(0);
  await expect(page.getByRole("tab", { name: "Overview" })).toHaveCount(0);
});
