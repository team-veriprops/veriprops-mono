"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@3rdparty/ui/button";
import { Input } from "@3rdparty/ui/input";
import { Label } from "@3rdparty/ui/label";
import { toast } from "@components/3rdparty/ui/use-toast";
import WizardOverlay from "@components/ui/wizard/WizardOverlay";
import { ROUTES } from "@lib/routes";
import { getCurrencySymbol, TransactionCurrency } from "@/types/models";
import { PaymentMethodKind, VerificationStatus } from "@/types/verification";
import { OtpChannel } from "@components/website/auth/models";
import {
  useCurrentSession,
  useSendOtpMutation,
  useVerifyOtpMutation,
} from "@components/website/auth/libs/useAuthQueries";
import {
  useInitiatePaymentMutation,
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
  const sendOtp = useSendOtpMutation();
  const verifyOtp = useVerifyOtpMutation();
  const initiate = useInitiatePaymentMutation();
  const stubConfirm = useStubConfirmMutation();

  const [otp, setOtp] = useState("");
  const [otpSent, setOtpSent] = useState(false);
  const [txRef, setTxRef] = useState<string | null>(null);
  const [checkoutUrl, setCheckoutUrl] = useState<string | null>(null);

  const phoneVerified = !!session?.user?.phoneVerified;
  const idemKey = `${verificationId}-pay`;

  const onSendOtp = async () => {
    await sendOtp.mutateAsync({ channel: OtpChannel.PHONE });
    setOtpSent(true);
    toast({ title: "Code sent", description: "Enter the code sent to your phone." });
  };

  const onVerifyOtp = async () => {
    await verifyOtp.mutateAsync({ channel: OtpChannel.PHONE, code: otp });
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
          </div>
        )}

        {!phoneVerified ? (
          <div className="space-y-3 rounded-lg border border-border p-4" data-testid="verify-pay-phone-gate">
            <p className="text-sm text-foreground">Verify your phone number before paying.</p>
            {!otpSent ? (
              <Button onClick={onSendOtp} disabled={sendOtp.isPending} data-testid="verify-pay-send-otp">
                Send code
              </Button>
            ) : (
              <div className="space-y-2">
                <Label>Enter code</Label>
                <Input value={otp} onChange={(e) => setOtp(e.target.value)} data-testid="verify-pay-otp" />
                <Button onClick={onVerifyOtp} disabled={verifyOtp.isPending || !otp} data-testid="verify-pay-verify-otp">
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
