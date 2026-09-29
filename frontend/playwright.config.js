import { defineConfig, devices } from "@playwright/test";
import path from "node:path";

export default defineConfig({
  testDir: "./tests/e2e",
  // Rule configuration is process-wide, so mutable browser workflows run in order.
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://127.0.0.1:5175",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    // Keep mobile coverage on Chromium so the demo only needs one browser binary.
    { name: "mobile", use: { ...devices["iPhone 13"], browserName: "chromium" } },
  ],
  webServer: process.env.PLAYWRIGHT_SKIP_WEBSERVER ? undefined : [
    {
      command: "bash scripts/run_e2e_backend.sh",
      cwd: path.resolve(process.cwd(), ".."),
      url: "http://127.0.0.1:8012/api/health",
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: "VITE_API_BASE_URL=http://127.0.0.1:8012/api npm run dev -- --host 127.0.0.1 --port 5175",
      cwd: process.cwd(),
      url: "http://127.0.0.1:5175",
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
