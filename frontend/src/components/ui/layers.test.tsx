import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, it, expect, afterEach } from "vitest";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { Dialog, DialogContent, DialogTitle } from "@3rdparty/ui/dialog";
import { PAGE_OVERLAY_LAYER, PORTAL_LAYER_Z } from "./layers";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const SRC_ROOT = path.resolve(__dirname, "../..");
const VENDORED_DIR = path.join(SRC_ROOT, "components", "3rdparty");

/** Reads the numeric z-index out of a Tailwind `z-N` / `z-[N]` utility. */
function zOf(classes: string | undefined | null): number | null {
  const match = classes?.match(/(?:^|\s)z-\[?(\d+)\]?(?:\s|$)/);
  return match ? Number(match[1]) : null;
}

function sourceFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) return full === VENDORED_DIR ? [] : sourceFiles(full);
    return /\.tsx?$/.test(entry.name) && !/\.test\.tsx?$/.test(entry.name) ? [full] : [];
  });
}

describe("page overlay layer", () => {
  let root: Root | null = null;
  let host: HTMLElement | null = null;

  afterEach(() => {
    act(() => root?.unmount());
    host?.remove();
    root = null;
    host = null;
  });

  // A global modal (updated-terms re-acceptance, session recovery) can open while a full-screen
  // page layer is up. An open Radix modal disables pointer events everywhere else, so a page layer
  // painted above it leaves the user a visible screen they cannot use.
  it("sits below portaled dialogs", () => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    act(() =>
      root!.render(
        <Dialog open>
          <DialogContent aria-describedby={undefined}>
            <DialogTitle>Mandatory</DialogTitle>
          </DialogContent>
        </Dialog>,
      ),
    );

    const layer = zOf(PAGE_OVERLAY_LAYER)!;
    expect(layer).toBeLessThan(zOf(document.querySelector('[data-slot="dialog-overlay"]')?.className)!);
    expect(layer).toBeLessThan(zOf(document.querySelector('[data-slot="dialog-content"]')?.className)!);
    expect(zOf(document.querySelector('[data-slot="dialog-content"]')?.className)).toBe(PORTAL_LAYER_Z);
  });

  // Catches the next hand-rolled full-screen layer before it lands above the portal tier.
  it("is the ceiling for every fixed layer the app renders itself", () => {
    const files = sourceFiles(SRC_ROOT);
    expect(files.length).toBeGreaterThan(0);
    const offenders = files.flatMap((file) =>
      readFileSync(file, "utf8")
        .split(/\r?\n/)
        .map((line, i) => ({ line, at: `${path.relative(SRC_ROOT, file)}:${i + 1}` }))
        .filter(({ line }) => /\bfixed\b/.test(line) && (zOf(line.replace(/["'`]/g, " ")) ?? 0) > PORTAL_LAYER_Z)
        .map(({ at }) => at),
    );
    expect(offenders).toEqual([]);
  });
});
