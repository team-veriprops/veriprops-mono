import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    // Playwright's own run artifacts (gitignored). They ship bundled/minified JS that
    // would otherwise drown a local `pnpm lint` in thousands of findings after any UAT
    // run — CI never sees them because the directories don't exist there.
    "e2e/playwright-report/**",
    "e2e/test-results/**",
    "e2e/.auth/**",
  ]),
]);

export default eslintConfig;
