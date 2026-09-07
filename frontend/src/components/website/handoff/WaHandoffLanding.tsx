"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ArrowUpRight, Loader2, ShieldCheck } from "lucide-react";

import { Button } from "@3rdparty/ui/button";
import { httpClient } from "@/containers";
import { usePublicConfigQuery } from "@components/website/auth/libs/useAuthQueries";
import { ROUTES } from "@lib/routes";
import { getCurrencySymbol, TransactionCurrency } from "@/types/models";
import { HandoffContext, HandoffIntent, HandoffPayment } from "@/types/handoff";
import { waMeUrl } from "@lib/whatsapp";
import WhatsAppOptInControls from "@components/shared/whatsapp/WhatsAppOptInControls";
import { NO_WHATSAPP_CONSENT, WhatsAppConsent } from "@/types/whatsappConsent";
import { HandoffService } from "./libs/handoff-service";

const service = new HandoffService(httpClient);

/**
 * Landing page for a WhatsApp handoff link (PRD §26.4.2).
 *
 * Someone arrives here mid-conversation, from a chat, usually on a phone. Two things
 * follow from that and drive the whole component:
 *
 * **It must say where they left off.** "Picking up where you left off: payment for
 * VP-1042" is a spec requirement — silently losing the customer's context is a
 * violation, not a cosmetic gap. So nothing renders until redemption returns the case.
 *
 * **A dead link must not feel like a dead end.** Links expire in fifteen minutes and are
 * single-use, so hitting an expired one is normal, not exceptional. The recovery state
 * offers one tap back into the chat to ask for a new one — the bot resends **on request
 * only**, never automatically (§26.4.2).
 *
 * Only `pay` completes here. `upload` and `report` continue into the authenticated
 * portal, because canonical evidence (§26.1.6) and the report link (Decision B) belong
 * behind a real login rather than a forwardable link.
 */
export default function WaHandoffLanding({
  intent,
  token,
}: {
  intent: HandoffIntent;
  token: string;
}) {
  const { data: publicConfig } = usePublicConfigQuery();
  const [context, setContext] = useState<HandoffContext | null>(null);
  const [payment, setPayment] = useState<HandoffPayment | null>(null);
  const [failed, setFailed] = useState(false);
  const [paying, setPaying] = useState(false);
  // Both unticked until the customer says otherwise — §26.4.6's required default. The
  // landing has no session, so there is no prior state to read: this is a fresh capture.
  const [consent, setConsent] = useState<WhatsAppConsent>(NO_WHATSAPP_CONSENT);
  // Redemption spends the link, so it must fire exactly once even under React's
  // development double-invoke.
  const redeemed = useRef(false);

  useEffect(() => {
    if (redeemed.current) return;
    redeemed.current = true;
    service
      .redeem(intent, token)
      .then((res) => (res.data ? setContext(res.data) : setFailed(true)))
      .catch(() => setFailed(true));
  }, [intent, token]);

  /**
   * §26.4.6's two opt-ins, at the only moment this customer is ever asked (D76). Written on
   * toggle rather than on payment: the tick is the consent act, and a failed card must not
   * lose it. Optimistic locally so the box responds immediately on a phone connection, and
   * best-effort on the wire — a consent that fails to save must never block the payment.
   */
  const onConsentChange = async (next: WhatsAppConsent) => {
    setConsent(next);
    try {
      await service.setConsent({ utility: next.utility, marketing: next.marketing });
    } catch {
      setConsent(consent);
    }
  };

  const onPay = async () => {
    setPaying(true);
    try {
      const res = await service.initiatePayment();
      setPayment(res.data ?? null);
    } catch {
      setFailed(true);
    } finally {
      setPaying(false);
    }
  };

  if (failed) return <ExpiredLink number={publicConfig?.whatsappNumber} />;
  if (!context) return <Loading />;

  return (
    <Shell>
      <OriginBanner context={context} />

      {intent === HandoffIntent.PAY && (
        <PaySection
          context={context}
          payment={payment}
          paying={paying}
          onPay={onPay}
          consent={consent}
          onConsentChange={onConsentChange}
        />
      )}

      {intent === HandoffIntent.UPLOAD && (
        <ContinueInPortal
          href={ROUTES.PORTAL.VERIFICATION_EVIDENCE(context.caseId)}
          title="Continue on the website"
          body="Documents you upload in the portal become part of your verification file. Chat images don't — that's why this step happens here."
          cta="Go to documents"
        />
      )}

      {intent === HandoffIntent.REPORT && (
        <ContinueInPortal
          href={ROUTES.PORTAL.VERIFICATION_REPORT(context.caseId)}
          title="Sign in to read your report"
          body="Your report is only ever shown to your account, so no one who forwards this message can open it."
          cta="Open my report"
        />
      )}
    </Shell>
  );
}

// ── States ────────────────────────────────────────────────────────

function Loading() {
  return (
    <Shell>
      <div
        className="flex items-center gap-2 text-sm text-gray-500"
        data-testid="wa-handoff-loading"
      >
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
        Picking up where you left off…
      </div>
    </Shell>
  );
}

/**
 * Expired, already used, or simply not valid — deliberately one state. The backend
 * refuses to say which, so the page cannot say either, and a person who was forwarded
 * the message learns nothing from trying it.
 */
export function ExpiredLink({ number }: { number?: string }) {
  const backToChat = number ? waMeUrl(number, "web-wa-expired") : null;
  return (
    <Shell>
      <div className="space-y-4" data-testid="wa-handoff-expired">
        <h1 className="text-lg font-semibold text-brand-navy">This link has expired</h1>
        <p className="text-sm text-gray-600">
          Links from our chat last 15 minutes and work once, so they can&apos;t be reused if
          a message gets forwarded. Ask us for a fresh one and we&apos;ll send it straight
          away.
        </p>
        {backToChat && (
          <Button asChild data-testid="wa-handoff-new-link">
            <a href={backToChat} target="_blank" rel="noopener noreferrer">
              Get a new link on WhatsApp
            </a>
          </Button>
        )}
      </div>
    </Shell>
  );
}

export function OriginBanner({ context }: { context: HandoffContext }) {
  return (
    <div
      className="rounded-lg border border-border bg-brand-surface-low px-4 py-3"
      data-testid="wa-handoff-context"
    >
      <p className="text-sm text-brand-navy">
        Picking up where you left off: <strong>{LABEL_BY_INTENT[context.intent]}</strong> for{" "}
        <strong>{context.vid}</strong>.
      </p>
    </div>
  );
}

const LABEL_BY_INTENT: Record<HandoffIntent, string> = {
  [HandoffIntent.PAY]: "payment",
  [HandoffIntent.UPLOAD]: "your documents",
  [HandoffIntent.REPORT]: "your report",
};

function PaySection({
  context,
  payment,
  paying,
  onPay,
  consent,
  onConsentChange,
}: {
  context: HandoffContext;
  payment: HandoffPayment | null;
  paying: boolean;
  onPay: () => void;
  consent: WhatsAppConsent;
  onConsentChange: (next: WhatsAppConsent) => void;
}) {
  const currency = context.currency ?? TransactionCurrency.NGN;
  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-border p-4">
        <p className="text-sm text-muted-foreground">Amount due</p>
        <p className="text-2xl font-bold text-foreground" data-testid="wa-handoff-amount">
          {getCurrencySymbol(currency)}
          {((context.amountDueMinor ?? 0) / 100).toLocaleString(undefined, {
            maximumFractionDigits: 2,
          })}
        </p>
      </div>

      <PaymentPledge />

      {/* §26.4.6, D76 — the customer who arrived from chat is asked here or nowhere. */}
      <WhatsAppOptInControls consent={consent} onChange={onConsentChange} />

      {!payment ? (
        <Button onClick={onPay} disabled={paying} data-testid="wa-handoff-pay">
          {paying ? "Starting…" : "Pay now"}
        </Button>
      ) : (
        <div className="space-y-2" data-testid="wa-handoff-checkout">
          <p className="text-sm text-muted-foreground">
            Complete the payment on the secure checkout page.
          </p>
          {payment.checkoutUrl?.startsWith("http") && (
            <a
              href={payment.checkoutUrl}
              className="text-primary underline"
              data-testid="wa-handoff-checkout-link"
            >
              Open secure checkout
            </a>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * The standing payment pledge (§26.1.1), repeated at every payment handoff. It is the
 * customer's defence against an impersonator sending a lookalike link, which is exactly
 * the moment they are most exposed — so it is stated here, not just in the chat.
 */
export function PaymentPledge() {
  return (
    <div
      className="flex gap-2 rounded-lg border border-brand-viridian/30 bg-brand-viridian/5 px-3 py-2.5"
      data-testid="wa-handoff-pledge"
    >
      <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-brand-viridian" aria-hidden="true" />
      <p className="text-xs text-brand-navy">
        Payments only ever happen at <strong>veriprops.ng</strong> — check the address bar
        before you pay. We will never ask you to pay anywhere else.
      </p>
    </div>
  );
}

function ContinueInPortal({
  href,
  title,
  body,
  cta,
}: {
  href: string;
  title: string;
  body: string;
  cta: string;
}) {
  return (
    <div className="space-y-3" data-testid="wa-handoff-continue">
      <h2 className="text-base font-semibold text-brand-navy">{title}</h2>
      <p className="text-sm text-gray-600">{body}</p>
      <Button asChild>
        <Link href={href} data-testid="wa-handoff-continue-link">
          {cta}
          <ArrowUpRight className="ml-1 h-4 w-4" aria-hidden="true" />
        </Link>
      </Button>
    </div>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main className="mx-auto max-w-md px-5 py-10 space-y-5">{children}</main>
  );
}
