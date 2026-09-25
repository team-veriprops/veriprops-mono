import { describe, expect, it } from "vitest";
import { HttpError } from "@lib/FetchHttpClient";
import { RATE_LIMIT_LOCKOUT_AT } from "../schemas";
import { lockoutAfterFailure } from "./lockout";

const wrongPassword = new HttpError("Invalid username or password", "/sessions", { httpStatus: 401 });
const outage = new HttpError("Something went wrong on our side.", "/sessions", { httpStatus: 500 });
const offline = new HttpError("Network error", "/sessions", { kind: "network" });

describe("lockoutAfterFailure", () => {
  it("counts a rejected password", () => {
    expect(lockoutAfterFailure({ count: 1 }, wrongPassword).count).toBe(2);
  });

  it("locks the form once the attempts reach the limit", () => {
    const next = lockoutAfterFailure({ count: RATE_LIMIT_LOCKOUT_AT - 1 }, wrongPassword);

    expect(next.lockedUntil).toBeGreaterThan(Date.now());
  });

  it("does not count a server failure — the password may well have been right", () => {
    expect(lockoutAfterFailure({ count: RATE_LIMIT_LOCKOUT_AT - 1 }, outage))
      .toEqual({ count: RATE_LIMIT_LOCKOUT_AT - 1 });
  });

  it("does not count a lost connection", () => {
    expect(lockoutAfterFailure({ count: 2 }, offline)).toEqual({ count: 2 });
  });
});
