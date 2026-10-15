import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "coverage", "playwright-report", "test-results", "src/api/schema.d.ts"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  reactHooks.configs.flat.recommended,
  {
    languageOptions: { globals: globals.browser },
    rules: {
      // AGENTS.md rule 6: all backend calls go through src/api/client.ts.
      "no-restricted-globals": [
        "error",
        { name: "fetch", message: "Call the backend through src/api/client.ts instead." },
      ],
      "no-restricted-properties": [
        "error",
        { object: "window", property: "fetch", message: "Use src/api/client.ts." },
      ],
    },
  },
  {
    files: ["src/api/client.ts", "src/**/*.test.{ts,tsx}", "src/test/**"],
    rules: { "no-restricted-globals": "off", "no-restricted-properties": "off" },
  },
);
