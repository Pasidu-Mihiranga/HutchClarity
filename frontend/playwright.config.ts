import { defineConfig, devices } from "@playwright/test";

/**
 * End to end configuration (C05, #24).
 *
 * **Both servers are started by Playwright**, the API and the web app, because
 * the journey under test crosses them: the chat drives `/v1` and the receipt it
 * ends at is signed and verified by the backend. A suite that mocked the API
 * would pass with the flow disconnected, which is exactly the bug C05 fixed.
 *
 * The API runs in the `lite` profile, which needs only Python and no services
 * (ADR-0006), so this needs no Docker and no database.
 *
 * `reuseExistingServer` is on outside CI: a developer with `make dev` already
 * running should not have it fought over.
 */
export default defineConfig({
  testDir: "./e2e",
  // One worker. The journeys share the simulated world's subscriber, and two
  // of them disputing the same charge at once would be two tests fighting over
  // one balance.
  workers: 1,
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["list"]] : [["list"]],
  timeout: 60_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL: process.env.E2E_WEB_BASE ?? "http://127.0.0.1:3100",
    trace: "retain-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    {
      /**
       * A phone viewport (E6).
       *
       * The customer app is the one most people would use on a phone, and the
       * only thing that had ever checked it at that size was a human looking
       * at it. The specs here are the ones where layout at 393px decides
       * whether the journey works at all: the composer and the confirm sheet
       * in the chat, the sign-in form, and the receipt verdict.
       *
       * The console is deliberately not in this project. It is a desk tool on
       * a desktop, its tables do not reflow to a phone, and pretending
       * otherwise would be a test asserting something nobody asked the product
       * to do.
       */
      name: "mobile-chromium",
      use: { ...devices["Pixel 7"] },
      testMatch: [
        "**/dispute-charge.spec.ts",
        "**/login.spec.ts",
        "**/customer-receipt.spec.ts",
      ],
    },
  ],
  webServer: [
    {
      // The repository root is two levels up from this file's directory.
      command: "make -C .. dev-e2e",
      url: "http://127.0.0.1:8100/health",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      stdout: "pipe",
      stderr: "pipe",
    },
    {
      command: "npm run dev -w @clarity/customer-web -- --port 3100",
      url: "http://127.0.0.1:3100/clarity",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: { NEXT_PUBLIC_API_BASE: "http://127.0.0.1:8100" },
    },
    // The console and the verify page are separate apps, and FE01 retires the
    // static UI that used to serve all three from the backend. A suite that
    // covered only customer-web would have retired `desk.html` and
    // `verify.html` on no evidence at all.
    {
      command: "npm run dev -w @clarity/console -- --port 3101",
      url: "http://127.0.0.1:3101/desk",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: { NEXT_PUBLIC_API_BASE: "http://127.0.0.1:8100" },
    },
    {
      command: "npm run dev -w @clarity/verify -- --port 3102",
      url: "http://127.0.0.1:3102",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: { NEXT_PUBLIC_API_BASE: "http://127.0.0.1:8100" },
    },
  ],
});
