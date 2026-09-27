"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@3rdparty/ui/button";
import { toast } from "sonner";
import { getErrorMessage } from "@lib/errors";
import WizardOverlay from "@components/ui/wizard/WizardOverlay";
import { ROUTES } from "@lib/routes";
import { getCurrencySymbol, TransactionCurrency } from "@/types/models";
import { Payment, PaymentCheckoutKind, PaymentMethodKind, PriceRefresh } from "@/types/verification";
import { useCurrentSession } from "@components/website/auth/libs/useAuthQueries";
import {
  useInitiatePaymentMutation,
  useReconcilePaymentMutation,
  useRefreshLockMutation,
  useStubConfirmMutation,
  useVerificationQuery,
} from "@components/portal/libs/useVerificationQueries";
import {
  useSetWhatsAppConsentMutation,
  useWhatsAppConsentQuery,
} from "@components/account/libs/useWhatsAppConsentQueries";
import WhatsAppOptInControls from "@components/shared/whatsapp/WhatsAppOptInControls";
import {
  NO_WHATSAPP_CONSENT,
  WhatsAppConsent,
  WhatsAppConsentSource,
} from "@/types/whatsappConsent";
import { SUBMISSION_STEPS } from "./types";
import PayPhoneGate from "./PayPhoneGate";
import { PayReturn, payReturnOutcome } from "./payReturn";

/** How often, and how many times, the page re-asks while the gateway settles a charge. */
const CONFIRM_POLL_MS = 3_000;
const CONFIRM_POLL_LIMIT = 10;

/** One double-tap key per payment attempt: a retry after a failed charge must start a new
 *  charge, not replay the failed one. */
function newPayAttemptKey(verificationId: string): string {
  return `${verificationId}-pay-${crypto.randomUUID()}`;
}

function major(minor?: number): string {
  return ((minor ?? 0) / 100).toLocaleString(undefined, { maximumFractionDigits: 2 });
}

export default function PayContainer({ verificationId }: { verificationId: string }) {
  const router = useRouter();
  const { data: session, refetch: refetchSession } = useCurrentSession();
  const { data: verification, refetch: refetchVerification } = useVerificationQuery(verificationId);
  const initiate = useInitiatePaymentMutation();
  // `mutateAsync` is stable across renders, so the poll below keys on state, not identity.
  const { mutateAsync: reconcileAsync, isPending: reconciling } = useReconcilePaymentMutation();
  const stubConfirm = useStubConfirmMutation();
  const refreshLock = useRefreshLockMutation();
  // §26.4.6's two opt-ins, at the moment the spec names for capturing them.
  const { data: waConsent } = useWhatsAppConsentQuery();
  const setWaConsent = useSetWhatsAppConsentMutation(WhatsAppConsentSource.PAY_SCREEN);

  const [txRef, setTxRef] = useState<string | null>(null);
  // Re-lock guard (§17.1): a price that changed since the customer last saw it must be
  // acknowledged before payment — never a silent re-charge.
  const [priceUpdate, setPriceUpdate] = useState<PriceRefresh | null>(null);
  const relockRan = useRef(false);

  // Where the customer is after coming back from (or reloading) a checkout — always from the
  // backend's reconciliation with the gateway, never from the gateway's query parameters.
  const [returnState, setReturnState] = useState<PayReturn>(PayReturn.NONE);
  const [confirmPolls, setConfirmPolls] = useState(0);
  const [idemKey, setIdemKey] = useState(() => newPayAttemptKey(verificationId));
  // The open hosted charge's page, so a customer who left it can go back to the same charge
  // rather than open a second one.
  const [openCheckoutUrl, setOpenCheckoutUrl] = useState<string | null>(null);
  const reconcileRan = useRef(false);

  const phoneVerified = !!session?.user?.phoneVerified;

  const followPayment = useCallback((payment: Payment | null | undefined) => {
    const outcome = payReturnOutcome(payment);
    setReturnState(outcome);
    if (outcome === PayReturn.PAID) {
      router.push(ROUTES.PORTAL.VERIFICATION_CONFIRMED(verificationId));
    } else if (outcome === PayReturn.SECONDARY_PAID) {
      toast.success("Payment received");
      router.push(ROUTES.PORTAL.VERIFICATION_DETAIL(verificationId));
    } else if (outcome === PayReturn.FAILED) {
      setIdemKey(newPayAttemptKey(verificationId));
    } else if (outcome === PayReturn.STUB_PENDING && payment) {
      setTxRef(payment.txRef);
    } else if (outcome === PayReturn.CONFIRMING && payment) {
      setOpenCheckoutUrl(payment.checkoutUrl ?? null);
    }
  }, [router, verificationId]);

  const checkWithGateway = useCallback(async () => {
    try {
      const res = await reconcileAsync(verificationId);
      followPayment(res.data);
    } catch (err) {
      toast.error(getErrorMessage(err, "Could not check your payment. Please try again."));
    }
  }, [reconcileAsync, verificationId, followPayment]);

  // On entry, and on return from the gateway's hosted page, ask the backend where the
  // customer's payment stands. A charge whose webhook is late still settles here.
  useEffect(() => {
    if (reconcileRan.current) return;
    reconcileRan.current = true;
    void checkWithGateway();
  }, [checkWithGateway]);

  // While a hosted charge is unsettled, keep asking for a short while — one request at a
  // time: the next poll is scheduled only once the previous answer is in.
  useEffect(() => {
    if (returnState !== PayReturn.CONFIRMING || reconciling || confirmPolls >= CONFIRM_POLL_LIMIT) return;
    const timer = setTimeout(() => {
      setConfirmPolls((n) => n + 1);
      void checkWithGateway();
    }, CONFIRM_POLL_MS);
    return () => clearTimeout(timer);
  }, [returnState, reconciling, confirmPolls, checkWithGateway]);

  /** Leave an unfinished hosted charge behind and start a fresh one (a new double-tap key). */
  const startNewPayment = () => {
    setIdemKey(newPayAttemptKey(verificationId));
    setOpenCheckoutUrl(null);
    setConfirmPolls(0);
    setReturnState(PayReturn.NONE);
  };

  // On entry, re-lock an expired price. If the fresh price differs from the last shown
  // one, surface the mandatory "price updated" interstitial before allowing payment.
  useEffect(() => {
    if (relockRan.current) return;
    relockRan.current = true;
    refreshLock.mutateAsync(verificationId).then(async (res) => {
      if (res.data?.priceChanged) setPriceUpdate(res.data);
      await refetchVerification();
    }).catch(() => undefined);
  }, [verificationId, refreshLock, refetchVerification]);

  const onConsentChange = async (next: WhatsAppConsent) => {
    // Best-effort: a consent that fails to save must not block the payment the customer
    // came here to make. They can set it again in account settings.
    try {
      await setWaConsent.mutateAsync({
        utility: next.utility,
        marketing: next.marketing,
      });
    } catch {
      toast.success("Preference not saved", { description: "You can set this later under WhatsApp in your account settings." });
    }
  };

  const onPay = async () => {
    const res = await initiate.mutateAsync({
      id: verificationId,
      method: PaymentMethodKind.CARD,
      idempotencyKey: idemKey,
    });
    const payment = res.data;
    if (payment?.checkoutKind === PaymentCheckoutKind.HOSTED && payment.checkoutUrl) {
      // The customer pays on the gateway's page and comes back here to be reconciled.
      window.location.assign(payment.checkoutUrl);
      return;
    }
    setTxRef(payment?.txRef ?? null);
  };

  const onConfirmStub = async () => {
    if (!txRef) return;
    await stubConfirm.mutateAsync({ txRef, succeeded: true });
    // The same path as a hosted return, so an initial charge and a re-check or upgrade
    // charge each land where they belong.
    await checkWithGateway();
  };

  const close = () => router.push(ROUTES.PORTAL.VERIFICATIONS);

  return (
    <WizardOverlay
      steps={SUBMISSION_STEPS}
      current={3}
      onClose={close}
      title="Payment"
      testIdPrefix="verify-pay"
    >
      <div className="space-y-6" data-testid="verify-pay">
        {verification && (
          <div className="rounded-lg border border-border p-4">
            <p className="text-sm text-muted-foreground">Amount due (contractual)</p>
            <p className="text-2xl font-bold text-foreground">
              {getCurrencySymbol(TransactionCurrency.NGN)}
              {major(verification.priceLockedMinor)}
            </p>
            {/* Applied-discount summary (§17.1). */}
            {((verification.firstTimeDiscountMinor ?? 0) + (verification.referralCreditAppliedMinor ?? 0)) > 0 && (
              // emerald-700 keeps small discount text above the 4.5:1 contrast minimum on white.
              <div className="mt-2 space-y-1 text-sm text-emerald-700 dark:text-emerald-400" data-testid="verify-pay-discount">
                {verification.firstTimeDiscountMinor > 0 && (
                  <div className="flex justify-between">
                    <span>First-time discount</span>
                    <span>−{getCurrencySymbol(TransactionCurrency.NGN)}{major(verification.firstTimeDiscountMinor)}</span>
                  </div>
                )}
                {verification.referralCreditAppliedMinor > 0 && (
                  <div className="flex justify-between">
                    <span>Referral credit</span>
                    <span>−{getCurrencySymbol(TransactionCurrency.NGN)}{major(verification.referralCreditAppliedMinor)}</span>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Re-lock guard (§17.1): the customer must accept the updated price before paying. */}
        {priceUpdate && (
          <div className="space-y-3 rounded-lg border border-amber-500/40 bg-amber-500/5 p-4" data-testid="verify-pay-price-updated">
            <p className="text-sm font-semibold text-foreground">Price updated</p>
            <p className="text-sm text-muted-foreground">
              Your 24-hour price lock expired, so we refreshed your quote. The amount is now{" "}
              <span className="font-semibold text-foreground">
                {getCurrencySymbol(TransactionCurrency.NGN)}{major(priceUpdate.netPriceMinor)}
              </span>{" "}
              (was {getCurrencySymbol(TransactionCurrency.NGN)}{major(priceUpdate.previousPriceMinor)}).
            </p>
            <Button onClick={() => setPriceUpdate(null)} data-testid="verify-pay-accept-price">
              Continue with new price
            </Button>
          </div>
        )}

        {/*
          §26.4.6: the two WhatsApp opt-ins are captured **at payment confirmation**. They
          are written the moment a box is ticked rather than on a successful charge — the
          tick is the consent act, and tying it to a gateway outcome would lose it every
          time a card fails.
        */}
        {!priceUpdate && (
          <WhatsAppOptInControls
            consent={waConsent ?? NO_WHATSAPP_CONSENT}
            onChange={onConsentChange}
            disabled={setWaConsent.isPending}
          />
        )}

        {returnState === PayReturn.CONFIRMING && (
          <div className="space-y-3 rounded-lg border border-border p-4" data-testid="verify-pay-confirming" aria-live="polite">
            {confirmPolls < CONFIRM_POLL_LIMIT ? (
              <p className="text-sm text-muted-foreground">Confirming your payment with the gateway…</p>
            ) : (
              <>
                <p className="text-sm text-muted-foreground">
                  We have not had confirmation from the gateway yet. If you completed the payment,
                  it will show here shortly. If you left the checkout page before paying, go back
                  to it, or start again.
                </p>
                <div className="flex flex-col gap-2 sm:flex-row">
                  <Button
                    variant="outline"
                    onClick={() => { setConfirmPolls(0); void checkWithGateway(); }}
                    disabled={reconciling}
                    data-testid="verify-pay-check-again"
                  >
                    Check again
                  </Button>
                  {openCheckoutUrl && (
                    <Button asChild data-testid="verify-pay-return-to-checkout">
                      <a href={openCheckoutUrl}>Return to checkout</a>
                    </Button>
                  )}
                  <Button variant="ghost" onClick={startNewPayment} data-testid="verify-pay-start-new">
                    Start a new payment
                  </Button>
                </div>
              </>
            )}
          </div>
        )}

        {returnState === PayReturn.FAILED && (
          <p className="text-sm text-destructive" data-testid="verify-pay-failed" role="alert">
            Your last payment did not go through, and you have not been charged for it. You can try again.
          </p>
        )}

        {priceUpdate || !session?.user || returnState === PayReturn.CONFIRMING ? null : !phoneVerified ? (
          <PayPhoneGate user={session.user} onVerified={refetchSession} />
        ) : !txRef ? (
          <Button onClick={onPay} disabled={initiate.isPending} data-testid="verify-pay-initiate">
            {initiate.isPending ? "Starting…" : "Pay now"}
          </Button>
        ) : (
          <div className="space-y-3" data-testid="verify-pay-checkout">
            <p className="text-sm text-muted-foreground">
              Status: Processing. Complete the payment on the gateway.
            </p>
            {/* Deterministic completion in local/test/dev (backend PAYMENT_STUB_MODE). A live
                charge never reaches this block: it is sent to the gateway's hosted page. */}
            <Button onClick={onConfirmStub} disabled={stubConfirm.isPending} data-testid="verify-pay-confirm">
              I&apos;ve made the payment
            </Button>
          </div>
        )}
      </div>
    </WizardOverlay>
  );
}
