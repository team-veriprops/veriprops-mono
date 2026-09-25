import { HttpError } from "@lib/FetchHttpClient";

interface LogoutLifecycleDeps {
  setPendingLogout: (pending: boolean) => void;
  clearSession: () => void;
}

/**
 * The logout mutation's callbacks, kept free of React so the queueing rule can be tested directly.
 *
 * The logout is queued (`pendingLogout`, persisted) *before* the request goes out, and dequeued
 * only once the backend has answered — any real response means it was reached and cleared the
 * cookies. Queueing up front covers the page leaving mid-request (the sign-out failsafe), where no
 * callback ever runs: the next page's `usePendingLogoutRetry` re-sends it and ends the session.
 * A network failure or a timeout may never have landed, so it stays queued; a repeat is harmless.
 */
export function logoutLifecycle({ setPendingLogout, clearSession }: LogoutLifecycleDeps) {
  return {
    onMutate: () => setPendingLogout(true),
    onSuccess: () => setPendingLogout(false),
    onError: (error: unknown) => {
      if (error instanceof HttpError && error.kind === "response") setPendingLogout(false);
    },
    // Local state must clear regardless of outcome — the user should never appear logged in just
    // because the backend call failed.
    onSettled: () => clearSession(),
  };
}
