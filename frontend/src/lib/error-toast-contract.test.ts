/**
 * A failed request's toast goes through `getErrorMessage`.
 *
 * An `onError: () => toast.error("…")` handler throws the error away. The user loses the
 * backend's own 4xx explanation ("the dispute window has closed") and, on a 5xx, the
 * reference support needs to find the logged exception. The fixed sentence belongs in
 * `getErrorMessage(err, "…")` as the fallback instead.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const SRC = path.resolve(__dirname, "..");
// A mutation callback that takes no error, or a catch block that binds none, then toasts.
const DISCARDED_ERROR_TOAST = /onError:\s*\(\)\s*=>\s*toast\.error\(|catch\s*\{\s*toast\.error\(/;

function componentFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) return componentFiles(full);
    return /\.tsx$/.test(name) && !/\.test\.tsx$/.test(name) ? [full] : [];
  });
}

describe("error toast contract", () => {
  it("never toasts a request failure without reading the error", () => {
    const offenders = componentFiles(SRC).filter((file) => DISCARDED_ERROR_TOAST.test(readFileSync(file, "utf8")));
    expect(offenders.map((file) => path.relative(SRC, file))).toEqual([]);
  });
});
