"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@3rdparty/ui/button";
import { Input } from "@3rdparty/ui/input";
import { Label } from "@3rdparty/ui/label";
import { toast } from "@components/3rdparty/ui/use-toast";
import WizardOverlay from "@components/ui/wizard/WizardOverlay";
import { ROUTES } from "@lib/routes";
import { getCurrencySymbol, TransactionCurrency } from "@/types/models";
import { PaymentMethodKind, PriceRefresh, VerificationStatus } from "@/types/verification";
import {
  useCurrentSession,
  useSendPhoneOtpMutation,
  useVerifyPhoneMutation,
} from "@components/website/auth/libs/useAuthQueries";
import {
  useInitiatePaymentMutation,
  useRefreshLockMutation,
  useStubConfirmMutation,
  useVerificationQuery,
} from "@components/portal/libs/useVerificationQueries";
import { SUBMISSION_STEPS } from "./types";

function major(minor?: number): string {
  return ((minor ?? 0) / 100).toLocaleString(undefined, { maximumFractionDigits: 2 });
}

export default function PayContainer({ verificationId }: { verificationId: string }) {
  const router = useRouter();
  const { data: session, refetch: refetchSession } = useCurrentSession();
  const { data: verification, refetch: refetchVerification } = useVerificationQuery(verificationId);
  const sendPhoneOtp = useSendPhoneOtpMutation();
  const verifyPhone = useVerifyPhoneMutation();
  const initiate = useInitiatePaymentMutation();
  const stubConfirm = useStubConfirmMutation();
  const refreshLock = useRefreshLockMutation();

  const [otp, setOtp] = useState("");
  const [otpSent, setOtpSent] = useState(false);
  const [txRef, setTxRef] = useState<string | null>(null);
  const [checkoutUrl, setCheckoutUrl] = useState<string | null>(null);
  // Re-lock guard (§17.1): a price that changed since the customer last saw it must be
  // acknowledged before payment — never a silent re-charge.
  const [priceUpdate, setPriceUpdate] = useState<PriceRefresh | null>(null);
  const relockRan = useRef(false);

  const phoneVerified = !!session?.user?.phoneVerified;
  const idemKey = `${verificationId}-pay`;

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

  const onSendOtp = async () => {
    await sendPhoneOtp.mutateAsync();
    setOtpSent(true);
    toast({ title: "Code sent", description: "Enter the code sent to your phone." });
  };

  const onVerifyOtp = async () => {
    // Authenticated Phase-5 verification — flips the user's phoneVerified server-side (§5).
    await verifyPhone.mutateAsync(otp);
    await refetchSession();
    toast({ title: "Phone verified" });
  };

  const onPay = async () => {
    const res = await initiate.mutateAsync({
      id: verificationId,
      method: PaymentMethodKind.CARD,
      idempotencyKey: idemKey,
    });
    setTxRef(res.data?.txRef ?? null);
    setCheckoutUrl(res.data?.checkoutUrl ?? null);
  };

  const onConfirmStub = async () => {
    if (!txRef) return;
    await stubConfirm.mutateAsync({ txRef, succeeded: true });
    const updated = await refetchVerification();
    if (updated.data?.status === VerificationStatus.PAID) {
      router.push(ROUTES.PORTAL.VERIFICATION_CONFIRMED(verificationId));
    }
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
              <div className="mt-2 space-y-1 text-sm text-emerald-600 dark:text-emerald-400" data-testid="verify-pay-discount">
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

        {priceUpdate ? null : !phoneVerified ? (
          <div className="space-y-3 rounded-lg border border-border p-4" data-testid="verify-pay-phone-gate">
            <p className="text-sm text-foreground">Verify your phone number before paying.</p>
            {!otpSent ? (
              <Button onClick={onSendOtp} disabled={sendPhoneOtp.isPending} data-testid="verify-pay-send-otp">
                Send code
              </Button>
            ) : (
              <div className="space-y-2">
                <Label>Enter code</Label>
                <Input value={otp} onChange={(e) => setOtp(e.target.value)} data-testid="verify-pay-otp" />
                <Button onClick={onVerifyOtp} disabled={verifyPhone.isPending || !otp} data-testid="verify-pay-verify-otp">
                  Verify phone
                </Button>
              </div>
            )}
          </div>
        ) : !txRef ? (
          <Button onClick={onPay} disabled={initiate.isPending} data-testid="verify-pay-initiate">
            {initiate.isPending ? "Starting…" : "Pay now"}
          </Button>
        ) : (
          <div className="space-y-3" data-testid="verify-pay-checkout">
            <p className="text-sm text-muted-foreground">
              Status: Processing. Complete the payment on the gateway.
            </p>
            {checkoutUrl && checkoutUrl.startsWith("http") && (
              <a href={checkoutUrl} className="text-primary underline" data-testid="verify-pay-checkout-link">
                Open secure checkout
              </a>
            )}
            {/* Deterministic completion in local/test/dev (backend PAYMENT_STUB_MODE). */}
            <Button onClick={onConfirmStub} disabled={stubConfirm.isPending} data-testid="verify-pay-confirm">
              I&apos;ve made the payment
            </Button>
          </div>
        )}
      </div>
    </WizardOverlay>
  );
}
