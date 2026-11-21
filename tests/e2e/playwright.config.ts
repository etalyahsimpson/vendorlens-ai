import { defineConfig } from "@playwright/test";

/**
 * E2E configuration. The backend (FastAPI, default :8000) and the frontend
 * (vite preview, :4173) are started by the caller (see scripts/e2e-run.sh
 * or the CI workflow) - this config only targets them.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  outputDir: "test-results",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:4173",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
});
