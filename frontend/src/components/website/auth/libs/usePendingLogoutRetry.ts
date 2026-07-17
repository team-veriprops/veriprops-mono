"use client";

import { useEffect } from "react";
import { useAuthStore } from "./useAuthStore";
import { useLogoutMutation } from "./useAuthQueries";

/** Only flush when a logout is actually queued and no attempt is already in flight. */
export function shouldFlushPendingLogout(pendingLogout: boolean, isMutationPending: boolean): boolean {
  return pendingLogout && !isMutationPending;
}

/**
 * Flushes a logout that failed to reach the backend (offline click) as soon as
 * connectivity is available — on mount (covers a new tab / reopened browser
 * seeing the flag via the shared `veriprops-auth` localStorage key) and on the
 * `online` event (covers the same tab regaining connectivity), mirroring the
 * retry pattern in MediaUploadManager. A no-op whenever `pendingLogout` is false.
 *
 * Mounted once in `ClientWrapperProvider`, next to `useProactiveSessionRefresh`.
 */
export function usePendingLogoutRetry(): void {
  const logout = useLogoutMutation();

  useEffect(() => {
    const flush = () => {
      if (shouldFlushPendingLogout(useAuthStore.getState().pendingLogout, logout.isPending)) {
        logout.mutate();
      }
    };
    flush();
    window.addEventListener("online", flush);
    return () => window.removeEventListener("online", flush);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}
