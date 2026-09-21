import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

// Fonts are self-hosted through next/font (see app/layout.tsx). A stylesheet that pulls a font
// from a third-party origin at runtime makes every page's load wait on that origin.
describe("stylesheets", () => {
  it("import no fonts or styles from a remote origin at runtime", () => {
    const stylesheets = readdirSync(__dirname).filter((name) => name.endsWith(".css"));
    expect(stylesheets.length).toBeGreaterThan(0);

    for (const name of stylesheets) {
      const css = readFileSync(path.join(__dirname, name), "utf8");
      expect(css, name).not.toMatch(/@import\s+(url\()?\s*['"]?https?:/i);
    }
  });
});
