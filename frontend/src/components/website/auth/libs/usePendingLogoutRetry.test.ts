import { describe, expect, it } from "vitest";
import { shouldFlushPendingLogout } from "./usePendingLogoutRetry";

describe("shouldFlushPendingLogout", () => {
  it("flushes when a logout is queued and nothing is in flight", () => {
    expect(shouldFlushPendingLogout(true, false)).toBe(true);
  });

  it("is a no-op when nothing is queued", () => {
    expect(shouldFlushPendingLogout(false, false)).toBe(false);
  });

  it("does not double-fire while a mutation is already in flight", () => {
    expect(shouldFlushPendingLogout(true, true)).toBe(false);
  });

  it("is a no-op when nothing is queued even if a mutation is in flight", () => {
    expect(shouldFlushPendingLogout(false, true)).toBe(false);
  });
});
