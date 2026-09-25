"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, Home } from "lucide-react";

import { Button } from "@3rdparty/ui/button";
import { useGrantCustomerPersonaMutation } from "@components/website/auth/libs/useAuthQueries";
import { ROUTES } from "@lib/routes";
import { navigateAfterPersonaChange } from "@lib/session-navigation";

/**
 * Where an agent takes up the customer hat (PRD §3.2, additive) — the mirror of `/agents/apply`.
 *
 * An account that signed up through the agent path holds the AGENT persona alone, so `/portal/*`
 * is shut to it and there is no way to have a property verified. Granting the persona is what
 * opens it, and it has to happen before the navigation the route guard would otherwise refuse —
 * which is why this is a route under `/agents/*` rather than a link straight to the wizard.
 *
 * The grant runs in an **effect, never during render**, and the wait is acknowledged in words: it
 * is a round trip that re-mints the session, and a blank screen in the middle of it reads as the
 * click having done nothing. Unlike a §26.5 handoff link this is repeatable, so a failure offers
 * the retry rather than an explanation.
 */
export default function VerifyPropertyContainer() {
  const grant = useGrantCustomerPersonaMutation();
  const [failed, setFailed] = useState(false);
  // React's development double-invoke would otherwise fire two grants on mount.
  const started = useRef(false);

  const takeUpTheCustomerHat = useCallback(() => {
    setFailed(false);
    grant
      .mutateAsync()
      // A full load, not a client-side push: the grant rotated the session, and every route the
      // client prefetched while this account had no customer hat was answered by the guard's
      // redirect and cached. See `navigateAfterPersonaChange`.
      .then(() => navigateAfterPersonaChange(ROUTES.PORTAL.VERIFICATIONS_NEW))
      .catch(() => setFailed(true));
    // `grant` is a fresh object each render; depending on it would re-run the effect below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    takeUpTheCustomerHat();
  }, [takeUpTheCustomerHat]);

  return (
    <main className="min-h-screen flex items-center justify-center px-4 py-12">
      <div
        className="w-full max-w-md rounded-2xl p-6 bg-brand-surface-card shadow-card space-y-4"
        data-testid="agent-verify-property"
      >
        <span className="w-11 h-11 rounded-xl flex items-center justify-center bg-brand-viridian-xlight text-brand-viridian">
          <Home className="w-6 h-6" aria-hidden="true" />
        </span>
        <h1 className="text-xl font-bold text-brand-navy">Verify a property</h1>

        {failed ? (
          <>
            <p
              className="text-sm text-brand-on-surface-variant"
              data-testid="agent-verify-property-error"
            >
              We couldn&rsquo;t open your customer account just then. Please try again.
            </p>
            <Button
              onClick={takeUpTheCustomerHat}
              disabled={grant.isPending}
              data-testid="agent-verify-property-retry"
            >
              {grant.isPending ? "Trying again…" : "Try again"}
            </Button>
          </>
        ) : (
          <p
            className="flex items-center gap-2 text-sm text-brand-on-surface-variant"
            data-testid="agent-verify-property-loading"
          >
            <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
            Opening your customer account so you can request a verification…
          </p>
        )}
      </div>
    </main>
  );
}
