import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

/**
 * Component tests for customer-web (E6).
 *
 * `include` is only `.ts`/`.tsx` on purpose: `test/chat-copy.test.mjs` is a
 * `node:test` file that reads the two chat catalogues as text, needs no DOM
 * and no runner, and still runs through `node --test` from the `test` script.
 * Moving it would cost a dependency for nothing.
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
