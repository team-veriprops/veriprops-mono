import { describe, expect, it } from "vitest";
import { computeRefreshDelay } from "./useProactiveSessionRefresh";
import { SESSION_REFRESH_LEAD_MS } from "@lib/config/app";

describe("computeRefreshDelay", () => {
  const now = Date.parse("2026-07-17T12:00:00Z");

  it("schedules the refresh SESSION_REFRESH_LEAD_MS before expiry", () => {
    const expiry = new Date(now + 10 * 60_000).toISOString(); // 10 min out
    expect(computeRefreshDelay(expiry, now)).toBe(10 * 60_000 - SESSION_REFRESH_LEAD_MS);
  });

  it("clamps to an immediate refresh inside the lead window", () => {
    const expiry = new Date(now + SESSION_REFRESH_LEAD_MS / 2).toISOString();
    expect(computeRefreshDelay(expiry, now)).toBe(0);
  });

  it("clamps to an immediate refresh when the token is already expired", () => {
    const expiry = new Date(now - 60_000).toISOString();
    expect(computeRefreshDelay(expiry, now)).toBe(0);
  });

  it("returns null (never schedules) for an unparseable timestamp", () => {
    expect(computeRefreshDelay("not-a-date", now)).toBeNull();
  });
});
