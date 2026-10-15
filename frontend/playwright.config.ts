import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests: a real browser against the production frontend build and
 * the real backend with a fresh SQLite database. The backend uses the fake
 * agent, so no API keys are needed (CI has none).
 *
 * Ports 8001 and 4173 are used so a running dev setup (8000/5173) is untouched.
 */
const BACKEND_PORT = 8001;
const FRONTEND_PORT = 4173;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1, // tests share one database
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://localhost:${FRONTEND_PORT}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command:
        "rm -f e2e.db && uv run alembic upgrade head && " +
        `uv run uvicorn app.main:create_app --factory --port ${BACKEND_PORT}`,
      cwd: "../backend",
      env: { DATABASE_URL: "sqlite:///./e2e.db", AGENT_MODE: "fake", RATE_LIMIT_PER_MINUTE: "1000" },
      url: `http://localhost:${BACKEND_PORT}/api/health`,
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: `npm run build && npx vite preview --port ${FRONTEND_PORT} --strictPort`,
      env: { VITE_BACKEND_URL: `http://localhost:${BACKEND_PORT}` },
      url: `http://localhost:${FRONTEND_PORT}`,
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
