import { describe, it, expect, beforeEach } from "vitest";
import { getDeviceFingerprint } from "./fingerprint";

describe("getDeviceFingerprint", () => {
  beforeEach(() => {
    if (typeof window !== "undefined") {
      window.localStorage.clear();
    }
  });

  it("returns a non-empty 8-char hex hash", () => {
    const fp = getDeviceFingerprint();
    expect(fp).toMatch(/^[0-9a-f]{8}$/);
  });

  it("is stable across calls within the same browser", () => {
    const a = getDeviceFingerprint();
    const b = getDeviceFingerprint();
    expect(a).toBe(b);
  });
});
