import { defineConfig } from "vitest/config";
import path from "path";

export default defineConfig({
  test: {
    environment: "jsdom",
    globals: false,
    // `e2e/` is the Playwright UAT suite (its own runner + config) — Vitest must not
    // collect those specs: `test.describe` there is Playwright's, not Vitest's.
    exclude: ["node_modules", ".next", "e2e"],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
      "@app": path.resolve(__dirname, "./src/app"),
      "@components": path.resolve(__dirname, "./src/components"),
      "@3rdparty": path.resolve(__dirname, "./src/components/3rdparty"),
      "@lib": path.resolve(__dirname, "./src/lib"),
      "@hooks": path.resolve(__dirname, "./src/hooks"),
      "@stores": path.resolve(__dirname, "./src/stores"),
      "@data": path.resolve(__dirname, "./src/data"),
      "@styles": path.resolve(__dirname, "./src/styles"),
      "@icons": path.resolve(__dirname, "./src/components/icons"),
      "@app-types": path.resolve(__dirname, "./src/types"),
      "@context": path.resolve(__dirname, "./src/context"),
    },
  },
});
