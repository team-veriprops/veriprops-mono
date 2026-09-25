"use client";

import { Loader2 } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@3rdparty/ui/dialog";
import { useAuthStore } from "@components/website/auth/libs/useAuthStore";

/**
 * Globally-mounted busy state for signing out (see `ClientWrapperProvider`).
 *
 * Sign-out is a network round-trip followed by a redirect, and the control that started it
 * usually disappears on the very click that starts it — the desktop user menu unmounts as it
 * closes — so the acknowledgement has to live somewhere other than the button. Mounting it
 * app-wide means every sign-out control gets the same feedback without wiring of its own.
 *
 * Keyed on `signingOut` (a sign-out the user asked for), never on the logout mutation's
 * pending state: `usePendingLogoutRetry` drives that same mutation in the background when a
 * queued offline logout flushes, which must stay invisible.
 */
export default function SignOutOverlay() {
  const signingOut = useAuthStore((s) => s.signingOut);

  return (
    // Controlled with no `onOpenChange`, plus `preventOutsideClose`: the session is already
    // on its way out, so there is nothing to dismiss back to.
    <Dialog open={signingOut}>
      <DialogContent
        showCloseButton={false}
        preventOutsideClose
        className="sm:max-w-sm text-center"
        data-testid="signout-overlay"
      >
        <DialogHeader className="items-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-brand-viridian-light text-brand-viridian">
            <Loader2 className="h-6 w-6 animate-spin [animation-duration:1.6s]" aria-hidden />
          </div>
          <DialogTitle className="text-lg font-semibold text-brand-on-surface">
            Signing you out…
          </DialogTitle>
        </DialogHeader>

        <DialogDescription
          role="status"
          aria-live="polite"
          className="text-sm leading-relaxed text-brand-on-surface-variant"
        >
          We&apos;re ending your session on this device and taking you to the sign-in page.
        </DialogDescription>
      </DialogContent>
    </Dialog>
  );
}
