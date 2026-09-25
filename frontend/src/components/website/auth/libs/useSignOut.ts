"use client";

import { useCallback } from "react";
import { ROUTES } from "@lib/routes";
import { SIGN_OUT_MAX_WAIT_MS } from "@lib/config/app";
import { navigateAfterSignOut } from "@lib/session-navigation";
import { useAuthStore } from "./useAuthStore";
import { useLogoutMutation } from "./useAuthQueries";

interface SignOutDeps {
  /** Read through a getter, not a snapshot — the guard must see the live flag. */
  isSigningOut: () => boolean;
  setSigningOut: (signingOut: boolean) => void;
  logout: (options: { onSettled: () => void }) => void;
  leave: () => void;
}

/**
 * The sign-out sequence, kept free of React so it can be tested directly.
 *
 * Raises the overlay flag first so the press is acknowledged before the request goes out,
 * then leaves for the login page once the call settles — success *or* failure, because the
 * mutation clears local session state either way and a user left on a signed-in page with
 * no session is stranded. A failsafe covers the request never settling at all: `logout()`
 * sets no request timeout, and the overlay it raised cannot be dismissed.
 */
export function runSignOut({ isSigningOut, setSigningOut, logout, leave }: SignOutDeps): void {
  // A double-click, or Enter plus a click, must not fire two logouts.
  if (isSigningOut()) return;
  setSigningOut(true);

  let left = false;
  const leaveOnce = () => {
    if (left) return;
    left = true;
    clearTimeout(failsafe);
    leave();
  };
  const failsafe = setTimeout(leaveOnce, SIGN_OUT_MAX_WAIT_MS);

  logout({ onSettled: leaveOnce });
}

/**
 * The one way to sign out. Every sign-out control goes through this so the busy overlay,
 * the double-press guard and the redirect cannot drift between surfaces.
 *
 * The redirect is a full document load — see `navigateAfterSignOut` for why.
 */
export function useSignOut(): { signOut: () => void; isSigningOut: boolean } {
  const logout = useLogoutMutation();
  const isSigningOut = useAuthStore((s) => s.signingOut);

  const signOut = useCallback(() => {
    runSignOut({
      isSigningOut: () => useAuthStore.getState().signingOut,
      setSigningOut: useAuthStore.getState().setSigningOut,
      logout: ({ onSettled }) => logout.mutate(undefined, { onSettled }),
      leave: () => navigateAfterSignOut(ROUTES.AUTH.LOGIN),
    });
  }, [logout]);

  return { signOut, isSigningOut };
}
