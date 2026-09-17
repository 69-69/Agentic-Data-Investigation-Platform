import { defineConfig, devices } from "@playwright/test";
const port = process.env.FRONTEND_TEST_PORT || "3100";
export default defineConfig({
  testDir: "./e2e",
  testMatch: process.env.E2E_REAL_STACK ? "real.spec.ts" : "dashboard.spec.ts",
  timeout: 90000,
  fullyParallel: false,
  workers: 1,
  reporter: "list",
  use: { baseURL: `http://127.0.0.1:${port}`, trace: "retain-on-failure" },
  projects: [
    {
      name: "desktop",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 1000 },
      },
    },
    {
      name: "mobile",
      use: { ...devices["iPhone 13"], defaultBrowserType: "chromium" },
    },
  ],
  webServer: {
    command: `npm run start -- --port ${port}`,
    url: `http://127.0.0.1:${port}`,
    reuseExistingServer: false,
    timeout: 60000,
  },
});
