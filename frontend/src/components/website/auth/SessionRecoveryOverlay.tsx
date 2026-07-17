"use client";

import { useEffect, useRef } from "react";
import { useStore } from "zustand";
import { RefreshCw, ShieldAlert } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@3rdparty/ui/dialog";
import { Button } from "@3rdparty/ui/button";
import { cn } from "@lib/utils";
import { SESSION_EXPIRED_REDIRECT_DELAY_MS } from "@lib/config/app";
import { consumeRefreshedSession, sessionRecoveryStore } from "@lib/sessionRecovery";
import { useAuthStore } from "@components/website/auth/libs/useAuthStore";

/**
 * Globally-mounted session-recovery dialog (see `ClientWrapperProvider`).
 *
 * Driven by the `sessionRecoveryStore` bridge that `FetchHttpClient` publishes
 * to: invisible for routine refreshes, a blocking "Reconnecting…" state while
 * the transient-failure retry budget is being spent, and a "Session expired"
 * handoff (brief pause + "Sign in now") once the session is unrecoverable.
 * Also hosts the React side of the bridge: piping refreshed session DTOs into
 * `useAuthStore` and clearing it on expiry.
 */
export default function SessionRecoveryOverlay() {
  const phase = useStore(sessionRecoveryStore, (s) => s.phase);
  const attempt = useStore(sessionRecoveryStore, (s) => s.attempt);
  const maxAttempts = useStore(sessionRecoveryStore, (s) => s.maxAttempts);
  const redirectTo = useStore(sessionRecoveryStore, (s) => s.redirectTo);
  const refreshedSession = useStore(sessionRecoveryStore, (s) => s.refreshedSession);
  const navigatedRef = useRef(false);

  // Bridge: every successful refresh re-syncs the persisted session mirror so
  // the proactive keep-alive reschedules from the fresh accessTokenExpiresAt.
  useEffect(() => {
    const session = consumeRefreshedSession();
    if (session) {
      useAuthStore.getState().setSession(session);
    }
  }, [refreshedSession]);

  // Expired: drop the dead client-side session, pause just long enough for the
  // user to read why, then hand off to login (which round-trips ?redirect=).
  useEffect(() => {
    if (phase !== "expired" || !redirectTo) return;
    useAuthStore.getState().clear();
    const timer = setTimeout(() => {
      if (!navigatedRef.current) {
        navigatedRef.current = true;
        window.location.assign(redirectTo);
      }
    }, SESSION_EXPIRED_REDIRECT_DELAY_MS);
    return () => clearTimeout(timer);
  }, [phase, redirectTo]);

  const signInNow = () => {
    if (redirectTo && !navigatedRef.current) {
      navigatedRef.current = true;
      window.location.assign(redirectTo);
    }
  };

  const expired = phase === "expired";

  return (
    // Controlled with no onOpenChange: not dismissible by escape/outside-click —
    // there is nothing meaningful to go back to mid-recovery.
    <Dialog open={phase !== "idle"}>
      <DialogContent
        showCloseButton={false}
        className="sm:max-w-sm text-center"
        data-testid="session-recovery-overlay"
      >
        <DialogHeader className="items-center">
          <div
            className={cn(
              "flex h-12 w-12 items-center justify-center rounded-full",
              expired ? "bg-amber-100 text-amber-600" : "bg-brand-viridian-light text-brand-viridian"
            )}
          >
            {expired ? (
              <ShieldAlert className="h-6 w-6" aria-hidden />
            ) : (
              <RefreshCw className="h-6 w-6 animate-spin [animation-duration:1.6s]" aria-hidden />
            )}
          </div>
          <DialogTitle className="text-lg font-semibold text-brand-on-surface">
            {expired ? "Your session has expired" : "Reconnecting your session"}
          </DialogTitle>
        </DialogHeader>

        {expired ? (
          <>
            <p className="text-sm leading-relaxed text-brand-on-surface-variant">
              For your security, you&apos;ve been signed out. We&apos;re taking you to sign
              in — you&apos;ll come right back to where you left off.
            </p>
            <Button className="w-full" onClick={signInNow} data-testid="session-signin-now">
              Sign in now
            </Button>
          </>
        ) : (
          <>
            <p className="text-sm leading-relaxed text-brand-on-surface-variant">
              Your connection was interrupted — we&apos;re retrying automatically. Your
              work stays right where it is.
            </p>
            <p
              aria-live="polite"
              data-testid="session-recovery-attempt"
              className="mx-auto rounded-full border border-brand-surface-dim px-3 py-1 text-xs font-medium tabular-nums text-brand-on-surface-variant"
            >
              Attempt {attempt} of {maxAttempts}
            </p>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
