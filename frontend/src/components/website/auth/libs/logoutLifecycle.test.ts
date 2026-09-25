import { describe, expect, it, vi } from "vitest";
import { HttpError } from "@lib/FetchHttpClient";
import { logoutLifecycle } from "./logoutLifecycle";

function harness() {
  const setPendingLogout = vi.fn();
  const clearSession = vi.fn();
  const lifecycle = logoutLifecycle({ setPendingLogout, clearSession });
  return { lifecycle, setPendingLogout, clearSession };
}

const networkError = () => new HttpError("Network error", "/users/auth/sessions/current", { kind: "network" });
const serverError = () =>
  new HttpError("Something went wrong", "/users/auth/sessions/current", { kind: "response", httpStatus: 500 });

describe("logoutLifecycle", () => {
  it("queues the logout before the request goes out, so a page that leaves first still has it on record", () => {
    // The sign-out failsafe can navigate while the call is in flight; the queued flag is what
    // lets the next page re-send it and actually end the session.
    const { lifecycle, setPendingLogout } = harness();

    lifecycle.onMutate();

    expect(setPendingLogout).toHaveBeenCalledWith(true);
  });

  it("clears the queue once the backend answered with success", () => {
    const { lifecycle, setPendingLogout } = harness();

    lifecycle.onMutate();
    lifecycle.onSuccess();

    expect(setPendingLogout).toHaveBeenLastCalledWith(false);
  });

  it("clears the queue on any real response — the backend was reached and cleared the cookies", () => {
    const { lifecycle, setPendingLogout } = harness();

    lifecycle.onMutate();
    lifecycle.onError(serverError());

    expect(setPendingLogout).toHaveBeenLastCalledWith(false);
  });

  it("keeps the logout queued when the request never reached the backend", () => {
    const { lifecycle, setPendingLogout } = harness();

    lifecycle.onMutate();
    lifecycle.onError(networkError());

    expect(setPendingLogout).toHaveBeenLastCalledWith(true);
  });

  it("keeps the logout queued after a timeout — it may never have landed, and a repeat is harmless", () => {
    const { lifecycle, setPendingLogout } = harness();

    lifecycle.onMutate();
    lifecycle.onError(new HttpError("Request aborted", "/users/auth/sessions/current", { kind: "timeout" }));

    expect(setPendingLogout).toHaveBeenLastCalledWith(true);
  });

  it("clears local session state whatever the outcome", () => {
    const { lifecycle, clearSession } = harness();

    lifecycle.onSettled();

    expect(clearSession).toHaveBeenCalledTimes(1);
  });
});
