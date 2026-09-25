import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { runSignOut } from "./useSignOut";
import { SIGN_OUT_MAX_WAIT_MS } from "@lib/config/app";

/** A controllable stand-in for the logout mutation: `settle()` fires its `onSettled`. */
function fakeLogout() {
  let settle: (() => void) | undefined;
  const logout = vi.fn((opts: { onSettled: () => void }) => {
    settle = opts.onSettled;
  });
  return { logout, settle: () => settle?.() };
}

function harness(initiallySigningOut = false) {
  let signingOut = initiallySigningOut;
  const { logout, settle } = fakeLogout();
  const leave = vi.fn();
  const setSigningOut = vi.fn((value: boolean) => {
    signingOut = value;
  });
  const run = () =>
    runSignOut({ isSigningOut: () => signingOut, setSigningOut, logout, leave });
  return { run, logout, settle, leave, setSigningOut };
}

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe("runSignOut", () => {
  it("raises the overlay flag before the request goes out, so the press is acknowledged immediately", () => {
    const { run, setSigningOut, logout } = harness();

    run();

    expect(setSigningOut).toHaveBeenCalledWith(true);
    expect(setSigningOut.mock.invocationCallOrder[0]).toBeLessThan(
      logout.mock.invocationCallOrder[0],
    );
  });

  it("leaves for the login page once the backend call settles", () => {
    const { run, settle, leave } = harness();

    run();
    expect(leave).not.toHaveBeenCalled();

    settle();
    expect(leave).toHaveBeenCalledTimes(1);
  });

  it("still leaves when the call fails — local session state is already cleared, so staying put would strand the user signed-out on a signed-in page", () => {
    // `onSettled` is the failure path too: the mutation clears the store either way.
    const { run, settle, leave } = harness();

    run();
    settle();

    expect(leave).toHaveBeenCalledTimes(1);
  });

  it("leaves anyway when the request never settles — the overlay it raised cannot be dismissed", () => {
    const { run, leave } = harness();

    run();
    vi.advanceTimersByTime(SIGN_OUT_MAX_WAIT_MS);

    expect(leave).toHaveBeenCalledTimes(1);
  });

  it("does not navigate twice when the failsafe and the response race", () => {
    const { run, settle, leave } = harness();

    run();
    settle();
    vi.advanceTimersByTime(SIGN_OUT_MAX_WAIT_MS * 2);

    expect(leave).toHaveBeenCalledTimes(1);
  });

  it("ignores a second press while one is in flight, so a double-click cannot fire two logouts", () => {
    const { run, logout, setSigningOut } = harness();

    run();
    run();

    expect(logout).toHaveBeenCalledTimes(1);
    expect(setSigningOut).toHaveBeenCalledTimes(1);
  });

  it("is a no-op when a sign-out is already under way", () => {
    const { run, logout } = harness(true);

    run();

    expect(logout).not.toHaveBeenCalled();
  });
});
