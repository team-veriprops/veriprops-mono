"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";
import { Button } from "@3rdparty/ui/button";
import { httpClient } from "@/containers";
import { usePublicConfigQuery } from "@components/website/auth/libs/useAuthQueries";
import { waMeUrl } from "@lib/whatsapp";
import { PaymentStatus } from "@/types/verification";
import { HandoffService } from "./libs/handoff-service";
import { Shell } from "./WaHandoffLanding";

const service = new HandoffService(httpClient);

/** How often, and how many times, the page re-asks while the gateway settles the charge. */
const CONFIRM_POLL_MS = 3_000;
const CONFIRM_POLL_LIMIT = 10;

export enum ReturnView {
  CHECKING = "CHECKING",
  RECEIVED = "RECEIVED",
  FAILED = "FAILED",
  /** Unsettled after polling, or the grant is gone: the chat confirms it either way. */
  PENDING = "PENDING",
}

export function returnViewFor(status: PaymentStatus | null | undefined): ReturnView {
  if (status === PaymentStatus.SUCCEEDED) return ReturnView.RECEIVED;
  if (status === PaymentStatus.FAILED) return ReturnView.FAILED;
  return ReturnView.CHECKING;
}

/**
 * Where a WhatsApp handoff's hosted checkout returns the customer (§26.5).
 *
 * The customer has no session, only the grant cookie their payment link left, so this page
 * never shows case details. It asks the backend (grant-scoped) where the payment stands, which
 * also settles a charge whose webhook is late, and points back to the chat that will confirm.
 */
export default function WaPayReturn() {
  const { data: publicConfig } = usePublicConfigQuery();
  const [view, setView] = useState<ReturnView>(ReturnView.CHECKING);
  const [polls, setPolls] = useState(0);
  const [checking, setChecking] = useState(false);
  const started = useRef(false);

  const check = useCallback(async () => {
    setChecking(true);
    try {
      const res = await service.reconcilePayment();
      setView(returnViewFor(res.data?.status));
    } catch {
      // No grant (expired, or opened elsewhere): the WhatsApp confirmation still arrives.
      setView(ReturnView.PENDING);
    } finally {
      setChecking(false);
    }
  }, []);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    void check();
  }, [check]);

  useEffect(() => {
    if (view !== ReturnView.CHECKING || checking || polls >= CONFIRM_POLL_LIMIT) return;
    const timer = setTimeout(() => {
      setPolls((n) => n + 1);
      void check();
    }, CONFIRM_POLL_MS);
    return () => clearTimeout(timer);
  }, [view, checking, polls, check]);

  // Still unsettled once polling is spent: the WhatsApp confirmation will say how it ended.
  const shown = view === ReturnView.CHECKING && polls >= CONFIRM_POLL_LIMIT ? ReturnView.PENDING : view;
  const backToChat = publicConfig?.whatsappNumber ? waMeUrl(publicConfig.whatsappNumber, "web-wa-pay-return") : null;

  return (
    <Shell>
      <div className="space-y-4" data-testid={`wa-pay-return-${shown.toLowerCase()}`} aria-live="polite">
        {shown === ReturnView.CHECKING && (
          <>
            <h1 className="text-lg font-semibold text-brand-navy">Confirming your payment…</h1>
            <p className="flex items-center gap-2 text-sm text-gray-600">
              <Loader2 className="size-4 animate-spin" aria-hidden /> This usually takes a few seconds.
            </p>
          </>
        )}
        {shown === ReturnView.RECEIVED && (
          <>
            <h1 className="text-lg font-semibold text-brand-navy">Payment received</h1>
            <p className="text-sm text-gray-600">
              Thank you. Your verification is starting, and we&apos;ll keep you updated on WhatsApp.
            </p>
          </>
        )}
        {shown === ReturnView.FAILED && (
          <>
            <h1 className="text-lg font-semibold text-brand-navy">Your payment didn&apos;t go through</h1>
            <p className="text-sm text-gray-600">
              You haven&apos;t been charged. Ask us on WhatsApp for a new payment link and try again.
            </p>
          </>
        )}
        {shown === ReturnView.PENDING && (
          <>
            <h1 className="text-lg font-semibold text-brand-navy">We&apos;re still waiting for confirmation</h1>
            <p className="text-sm text-gray-600">
              If you completed the payment, we&apos;ll confirm it on WhatsApp shortly. If you left the
              checkout before paying, ask us there for a new link.
            </p>
          </>
        )}
        {shown !== ReturnView.CHECKING && backToChat && (
          <Button asChild data-testid="wa-pay-return-chat">
            <a href={backToChat}>Back to WhatsApp</a>
          </Button>
        )}
      </div>
    </Shell>
  );
}
