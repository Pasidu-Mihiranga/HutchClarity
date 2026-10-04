import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

/**
 * Component tests for the console (E6).
 *
 * Mirrors `packages/ui/vitest.config.ts`: jsdom, globals, and esbuild's
 * automatic JSX rather than `@vitejs/plugin-react`, which keeps one fewer
 * dependency in the tree (I17 asks for a licence note on each new one).
 *
 * The `@` alias has to be restated here because `next lint` and `tsc` read it
 * from `tsconfig.json` and Vitest does not.
 */
export default defineConfig({
  esbuild: { jsx: "automatic" },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL(".", import.meta.url)),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./test/setup.ts"],
    include: ["test/**/*.test.{ts,tsx}"],
  },
});
