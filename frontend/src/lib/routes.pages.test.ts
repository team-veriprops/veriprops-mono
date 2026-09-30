import { readdirSync } from "node:fs";
import path from "node:path";
import { describe, it, expect } from "vitest";

import { ROUTES } from "./routes";

const APP_DIR = path.resolve(__dirname, "../app");

/** Every page's URL pattern, route groups `(x)` dropped: `["admin", "finance", "[id]"]`. */
function pagePatterns(dir: string, segments: string[] = []): string[][] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    if (entry.isFile() && /^page\.(tsx|ts|jsx|js)$/.test(entry.name)) return [segments];
    if (!entry.isDirectory()) return [];
    const group = /^\(.*\)$/.test(entry.name);
    return pagePatterns(path.join(dir, entry.name), group ? segments : [...segments, entry.name]);
  });
}

/** Every static page path declared in ROUTES (builders and API/external links skipped). */
function declaredPaths(node: unknown, key = "ROUTES"): [string, string][] {
  if (typeof node === "string") {
    const isPage = node.startsWith("/") && !node.startsWith("/api/") && !node.includes("?") && !node.includes("#");
    return isPage ? [[key, node]] : [];
  }
  if (node && typeof node === "object") {
    return Object.entries(node).flatMap(([k, v]) => declaredPaths(v, `${key}.${k}`));
  }
  return [];
}

const matches = (url: string, pattern: string[]) => {
  const parts = url.split("/").filter(Boolean);
  if (pattern.some((p) => p.startsWith("[..."))) return parts.length >= pattern.length - 1;
  return parts.length === pattern.length && pattern.every((p, i) => p.startsWith("[") || p === parts[i]);
};

// Routes declared ahead of their pages. Each carries a `TODO(gap)` marker in routes.ts and a
// §G row in MASTER-PRD; a new entry here needs both, and building the page removes it.
const DECLARED_GAPS = new Set([
  "ROUTES.ADMIN.FRAUD_FLAGS",
  "ROUTES.ADMIN.CONTENT",
  "ROUTES.ADMIN.CONTENT_HOW_IT_WORKS",
  "ROUTES.ADMIN.CONTENT_FAQS",
  "ROUTES.ADMIN.CONTENT_TESTIMONIALS",
  "ROUTES.ADMIN.CONTENT_AGENT_SPOTLIGHTS",
  "ROUTES.ADMIN.CONTENT_AREA_INSIGHTS",
  "ROUTES.PORTAL.PAYMENTS",
]);

describe("ROUTES", () => {
  it("has a page behind every path it declares, apart from the declared gaps", () => {
    const pages = pagePatterns(APP_DIR);
    const orphans = declaredPaths(ROUTES)
      .filter(([key]) => !DECLARED_GAPS.has(key))
      .filter(([, url]) => !pages.some((pattern) => matches(url, pattern)))
      .map(([key, url]) => `${key} → ${url}`);
    expect(orphans).toEqual([]);
  });

  it("keeps no gap on the list once its page exists", () => {
    const pages = pagePatterns(APP_DIR);
    const built = declaredPaths(ROUTES)
      .filter(([key, url]) => DECLARED_GAPS.has(key) && pages.some((pattern) => matches(url, pattern)))
      .map(([key]) => key);
    expect(built).toEqual([]);
  });
});
