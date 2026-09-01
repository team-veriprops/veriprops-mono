"use client";

import { useEffect, useRef, useState } from "react";
import { Loader2, MessageCircle, ShieldCheck } from "lucide-react";

import { Button } from "@3rdparty/ui/button";
import { usePublicConfigQuery } from "@components/website/auth/libs/useAuthQueries";
import {
  useConfirmWhatsAppLinkFromTokenMutation,
  useStartWhatsAppLinkFromTokenMutation,
} from "@components/account/libs/useWhatsAppLinkQueries";
import { getErrorMessage } from "@lib/utils";
import { waMeUrl } from "@lib/whatsapp";

/**
 * WhatsApp→web account linking landing (PRD §7.4.4, WA-24).
 *
 * The bot sends this link to a number it cannot yet attribute to anyone. Getting here
 * means the customer has signed in — `proxy.ts` guarantees that — so the only remaining
 * question is whether they control the number the bot messaged.
 *
 * The number is **never** taken from the URL query or from this page's state: it comes
 * back from the server, out of the signed token. That is what stops a signed-in attacker
 * from having a code posted to a number the bot never contacted.
 *
 * A dead link gets the same treatment as the other handoff landings — one state, no
 * explanation. Expired, already used, and forged must be indistinguishable.
 */
export default function WaLinkLanding({ token }: { token: string }) {
  const { data: publicConfig } = usePublicConfigQuery();
  const startLink = useStartWhatsAppLinkFromTokenMutation();
  const confirmLink = useConfirmWhatsAppLinkFromTokenMutation();

  const [number, setNumber] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [linked, setLinked] = useState(false);
  const [failed, setFailed] = useState(false);
  const [codeError, setCodeError] = useState<string | null>(null);
  // Sending the code is a side effect with a rate limit behind it, so it must fire once
  // even under React's development double-invoke.
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    startLink
      .mutateAsync(token)
      .then((challenge) => setNumber(challenge?.phoneE164 ?? null))
      .catch(() => setFailed(true));
  }, [startLink, token]);

  const onConfirm = async () => {
    setCodeError(null);
    try {
      await confirmLink.mutateAsync({ token, code });
      setLinked(true);
    } catch (err) {
      setCodeError(getErrorMessage(err as Error, "That code didn't match. Try again."));
    }
  };

  if (failed) return <DeadLink number={publicConfig?.whatsappNumber} />;
  if (linked) return <Linked number={publicConfig?.whatsappNumber} />;
  if (!number) return <Loading />;

  return (
    <Shell>
      <p className="text-sm text-brand-on-surface-variant" data-testid="wa-link-landing-origin">
        We sent a 6-digit code to <span className="font-medium text-foreground">{number}</span>{" "}
        on WhatsApp. Enter it here to connect that number to this account.
      </p>
      <input
        inputMode="numeric"
        autoComplete="one-time-code"
        maxLength={6}
        value={code}
        onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
        placeholder="654123"
        data-testid="wa-link-landing-code"
        className="flex h-11 w-44 rounded-md border border-input bg-background px-3 py-2 text-base outline-none focus:ring-2 focus:ring-ring"
      />
      {codeError && <p className="text-sm text-destructive">{codeError}</p>}
      <Button
        onClick={onConfirm}
        disabled={code.length < 6 || confirmLink.isPending}
        data-testid="wa-link-landing-confirm"
      >
        {confirmLink.isPending && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
        Connect this number
      </Button>
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main className="min-h-screen flex items-center justify-center px-4 py-12">
      <div
        className="w-full max-w-md rounded-2xl p-6 bg-brand-surface-card shadow-card space-y-4"
        data-testid="wa-link-landing"
      >
        <span className="w-11 h-11 rounded-xl flex items-center justify-center bg-brand-viridian-xlight text-brand-viridian">
          <MessageCircle className="w-6 h-6" />
        </span>
        <h1 className="text-xl font-bold text-brand-navy">Connect your WhatsApp</h1>
        {children}
      </div>
    </main>
  );
}

function Loading() {
  return (
    <Shell>
      <p className="flex items-center gap-2 text-sm text-brand-on-surface-variant">
        <Loader2 className="w-4 h-4 animate-spin" /> Sending your code…
      </p>
    </Shell>
  );
}

function Linked({ number }: { number?: string }) {
  const waLink = waMeUrl(number ?? "", "web-wa-link");
  return (
    <Shell>
      <p className="flex items-start gap-2 text-sm text-brand-on-surface-variant" data-testid="wa-link-landing-done">
        <ShieldCheck className="w-5 h-5 shrink-0 text-brand-viridian" />
        Your WhatsApp number is connected. Head back to the chat and our assistant will
        pick up where you left off.
      </p>
      {waLink && (
        <a href={waLink} target="_blank" rel="noopener noreferrer">
          <Button data-testid="wa-link-landing-return">Return to WhatsApp</Button>
        </a>
      )}
    </Shell>
  );
}

function DeadLink({ number }: { number?: string }) {
  const waLink = waMeUrl(number ?? "", "web-wa-link-expired");
  return (
    <Shell>
      {/* One state for expired, spent and forged — the difference is not the customer's
          business, and telling a prober which one it was classifies the link for them. */}
      <p className="text-sm text-brand-on-surface-variant" data-testid="wa-link-landing-dead">
        This link is no longer valid. Links last 15 minutes and can only be used once.
        Message us on WhatsApp and we&rsquo;ll send you a fresh one.
      </p>
      {waLink && (
        <a href={waLink} target="_blank" rel="noopener noreferrer">
          <Button data-testid="wa-link-landing-new">Get a new link in WhatsApp</Button>
        </a>
      )}
    </Shell>
  );
}
