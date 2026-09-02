"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, ClipboardCheck } from "lucide-react";

import { Button } from "@3rdparty/ui/button";
import { usePublicConfigQuery } from "@components/website/auth/libs/useAuthQueries";
import { httpClient } from "@/containers";
import { HandoffService } from "./libs/handoff-service";
import { ROUTES } from "@lib/routes";
import { waMeUrl } from "@lib/whatsapp";

const service = new HandoffService(httpClient);

/**
 * Chat-intake landing (PRD §5.1, §7.5, D69).
 *
 * The bot collected four answers over WhatsApp and sent this link. Getting here means the
 * customer has signed in — `proxy.ts` guarantees it — which is the thing the chat could
 * not establish. Redeeming seeds their draft with what they told the bot and sends them
 * into the **existing** submission wizard, so the §5.1 fields the chat skipped, the tier
 * step, the §5.3 consent control and payment are all the ones already built and tested.
 *
 * Redemption runs in an **effect, never during render**: the link is single-use, and
 * WhatsApp fetches the URL to build its preview card. A dead link gets the same one state
 * as every other handoff landing — expired, spent and forged are not distinguishable, and
 * saying which one it was would classify the link for whoever is probing.
 */
export default function WaIntakeLanding({ token }: { token: string }) {
  const router = useRouter();
  const { data: publicConfig } = usePublicConfigQuery();
  const [failed, setFailed] = useState(false);
  // Single-use, so it must fire exactly once even under React's development double-invoke.
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    service
      .redeemIntake(token)
      .then((res) => {
        if (!res?.data?.verificationId) {
          setFailed(true);
          return;
        }
        // Straight into the wizard, which resumes the draft we just seeded. `replace` so
        // the back button does not return to a link that is now spent.
        router.replace(ROUTES.PORTAL.VERIFICATIONS_NEW);
      })
      .catch(() => setFailed(true));
  }, [router, token]);

  if (failed) return <DeadLink number={publicConfig?.whatsappNumber} />;
  return <Loading />;
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main className="min-h-screen flex items-center justify-center px-4 py-12">
      <div
        className="w-full max-w-md rounded-2xl p-6 bg-brand-surface-card shadow-card space-y-4"
        data-testid="wa-intake-landing"
      >
        <span className="w-11 h-11 rounded-xl flex items-center justify-center bg-brand-viridian-xlight text-brand-viridian">
          <ClipboardCheck className="w-6 h-6" />
        </span>
        <h1 className="text-xl font-bold text-brand-navy">Picking up your details</h1>
        {children}
      </div>
    </main>
  );
}

function Loading() {
  return (
    <Shell>
      {/* §7.4.2 — the landing must acknowledge the context it picked up. Silently
          dropping the customer into a form would be the spec violation, not a rough edge. */}
      <p
        className="flex items-center gap-2 text-sm text-brand-on-surface-variant"
        data-testid="wa-intake-landing-loading"
      >
        <Loader2 className="w-4 h-4 animate-spin" />
        Bringing over what you told us on WhatsApp…
      </p>
    </Shell>
  );
}

function DeadLink({ number }: { number?: string }) {
  const waLink = waMeUrl(number ?? "", "web-wa-intake-expired");
  return (
    <Shell>
      <p className="text-sm text-brand-on-surface-variant" data-testid="wa-intake-landing-dead">
        This link is no longer valid. Links last 15 minutes and can only be used once.
        Message us on WhatsApp and we&rsquo;ll send you a fresh one — your answers are
        still there.
      </p>
      {waLink && (
        <a href={waLink} target="_blank" rel="noopener noreferrer">
          <Button data-testid="wa-intake-landing-new">Get a new link in WhatsApp</Button>
        </a>
      )}
    </Shell>
  );
}
