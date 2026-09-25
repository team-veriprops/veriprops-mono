import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const SRC_ROOT = path.resolve(__dirname, "..");

function tsxFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) return tsxFiles(full);
    return entry.name.endsWith(".tsx") && !entry.name.endsWith(".test.tsx") ? [full] : [];
  });
}

// A class naming a colour the theme does not define is not a build error in Tailwind v4 — it
// simply generates no CSS. That is how the 404 page shipped a white label on a transparent
// button. Every `*-brand-*` colour utility must resolve to a `--color-brand-*` theme token.
const BRAND_UTILITY =
  /(?:^|[\s"'`:])(?:bg|text|border(?:-[trblxy])?|ring|fill|stroke|outline|divide|placeholder|from|via|to|shadow|decoration)-(brand(?:-[a-z]+)*)(?:\/\d+)?(?=[\s"'`]|$)/g;

describe("theme colour tokens", () => {
  it("back every brand colour utility the app uses", () => {
    const theme = readFileSync(path.join(__dirname, "theme.css"), "utf8");
    const defined = new Set([...theme.matchAll(/--color-(brand[a-z-]*)\s*:/g)].map((m) => m[1]));
    expect(defined.size).toBeGreaterThan(0);

    const undefinedUses = tsxFiles(SRC_ROOT).flatMap((file) =>
      readFileSync(file, "utf8")
        .split(/\r?\n/)
        .flatMap((line, i) =>
          [...line.matchAll(BRAND_UTILITY)]
            .map((m) => m[1])
            .filter((token) => !defined.has(token))
            .map((token) => `${path.relative(SRC_ROOT, file)}:${i + 1} ${token}`),
        ),
    );
    expect(undefinedUses).toEqual([]);
  });
});
