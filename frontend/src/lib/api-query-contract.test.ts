/**
 * Query parameters on the wire use the backend's snake_case names.
 *
 * JSON bodies are camelCase through the backend's alias generator, but FastAPI binds query
 * parameters by their Python names, so `?pageSize=` is silently ignored and the endpoint falls
 * back to its default page size. That drift is invisible whenever the caller's size happens to
 * equal the default, so this guard scans every service for it.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const SRC = path.resolve(__dirname, "..");

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) return sourceFiles(full);
    const isSource = /\.(ts|tsx)$/.test(name) && !/\.test\.(ts|tsx)$/.test(name);
    return isSource ? [full] : [];
  });
}

describe("API query contract", () => {
  it("never sends a camelCase page size in a query string", () => {
    // A literal query string, or a URLSearchParams key.
    const camelPageSize = /[?&]pageSize=|\.(set|append)\(\s*["']pageSize["']/;
    const offenders = sourceFiles(SRC).filter((file) => camelPageSize.test(readFileSync(file, "utf8")));
    expect(offenders.map((file) => path.relative(SRC, file))).toEqual([]);
  });
});
