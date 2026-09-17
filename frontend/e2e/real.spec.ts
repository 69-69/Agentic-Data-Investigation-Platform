import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { mkdir } from "node:fs/promises";
import path from "node:path";
test("browser → Next proxy → Java → Python → SQL → results", async ({
  page,
}, info) => {
  await page.goto("/");
  if (process.env.CAPTURE_SCREENSHOTS) {
    await mkdir("../docs/screenshots", { recursive: true });
    await page.screenshot({
      path: path.resolve(
        `../docs/screenshots/dashboard-${info.project.name}.png`,
      ),
      fullPage: true,
    });
  }
  await page
    .getByRole("button", { name: "Volume decline", exact: true })
    .click();
  await page.getByRole("button", { name: "Run investigation" }).click();
  await expect(
    page.getByRole("heading", {
      name: "Why did transaction volume decline last week?",
    }),
  ).toBeVisible({ timeout: 75000 });
  await expect(
    page
      .getByText(/Ingested volume changed from 1400 to 700; decline 50.0%./)
      .first(),
  ).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  if (process.env.CAPTURE_SCREENSHOTS)
    await page.screenshot({
      path: path.resolve(`../docs/screenshots/result-${info.project.name}.png`),
      fullPage: true,
    });
  await page.getByRole("button", { name: "View evidence e1" }).click();
  await expect(
    page.getByRole("region", { name: "Evidence e1 rows" }),
  ).toContainText("1400");
  await page.getByRole("tab", { name: /SQL/ }).click();
  await page.locator("summary").first().click();
  await expect(page.getByLabel("SQL query s1", { exact: true })).toContainText(
    "LIMIT",
  );
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
