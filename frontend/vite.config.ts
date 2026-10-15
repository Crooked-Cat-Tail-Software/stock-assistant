import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// In development, Vite forwards /api to the FastAPI backend, so the browser
// sees one origin and no CORS configuration is needed. In Docker, nginx does
// the same job.
const backend = process.env.VITE_BACKEND_URL ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { "/api": backend },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    restoreMocks: true,
    include: ["src/**/*.test.{ts,tsx}"],
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/**/*.test.{ts,tsx}", "src/test/**", "src/main.tsx", "src/api/schema.d.ts"],
      reporter: ["text-summary", "text", "html"],
    },
  },
});
