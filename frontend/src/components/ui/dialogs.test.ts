import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, it, expect } from "vitest";

const SRC_ROOT = path.resolve(__dirname, "../..");
const VENDORED_DIR = path.join(SRC_ROOT, "components", "3rdparty");

function appSources(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) return full === VENDORED_DIR ? [] : appSources(full);
    return entry.name.endsWith(".tsx") && !entry.name.endsWith(".test.tsx") ? [full] : [];
  });
}

const count = (source: string, pattern: RegExp) => source.match(pattern)?.length ?? 0;

// A Radix dialog announces its title and then its description. Without one, a screen-reader user
// hears "Updated terms — please review" and nothing about what is being asked, and Radix logs a
// warning in every environment. A dialog with genuinely nothing to describe opts out explicitly
// with `aria-describedby={undefined}`.
describe("dialogs", () => {
  it("each describe themselves to assistive technology", () => {
    const files = appSources(SRC_ROOT);
    expect(files.length).toBeGreaterThan(0);

    const undescribed = files.filter((file) => {
      const source = readFileSync(file, "utf8");
      const dialogs = count(source, /<DialogContent\b/g);
      const described = count(source, /<DialogDescription\b/g) + count(source, /aria-describedby=/g);
      return dialogs > described;
    });
    expect(undescribed.map((file) => path.relative(SRC_ROOT, file))).toEqual([]);
  });
});
