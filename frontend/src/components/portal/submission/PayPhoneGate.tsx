"use client";

import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Button } from "@3rdparty/ui/button";
import { Input } from "@3rdparty/ui/input";
import { Label } from "@3rdparty/ui/label";
import { toast } from "@components/3rdparty/ui/use-toast";
import PhoneInputWithCountry from "@components/ui/form/PhoneInputWithCountry";
import { phoneFields, type PhoneFieldsValues } from "@components/website/auth/schemas";
import {
  useSendPhoneOtpMutation,
  useVerifyPhoneMutation,
} from "@components/website/auth/libs/useAuthQueries";
import { otpDeliveryError } from "@components/website/auth/libs/otpDelivery";
import type { AuthUser } from "@components/website/auth/models";
import { DEFAULT_DIAL_CODE } from "@lib/config/app";
import { getErrorMessage } from "@lib/utils";

type SessionPhone = Pick<AuthUser, "phone" | "phoneCountryCode" | "phoneDialCode">;

/** The gate starts from the number on the customer's profile (empty when they have none yet). */
export function phoneGateDefaults(user?: SessionPhone | null): PhoneFieldsValues {
  return {
    countryCode: user?.phoneCountryCode || "NG",
    dialCode: user?.phoneDialCode || DEFAULT_DIAL_CODE,
    phone: user?.phone ?? "",
  };
}

interface Props {
  user?: SessionPhone | null;
  /** Called once the backend has verified the number — refresh the session so the gate lifts. */
  onVerified: () => unknown;
}

/**
 * The pay-step phone gate (PRD §10.5). A customer's phone must be verified before their first
 * payment; here they confirm the number on file or correct it, then enter the OTP. The number is
 * only saved to their profile once the code is verified, and the backend rejects a number that
 * belongs to another account.
 */
export default function PayPhoneGate({ user, onVerified }: Props) {
  const sendOtp = useSendPhoneOtpMutation();
  const verifyPhone = useVerifyPhoneMutation();
  const form = useForm<PhoneFieldsValues>({
    resolver: zodResolver(phoneFields),
    defaultValues: phoneGateDefaults(user),
  });
  const [countryCode, dialCode, phone] = useWatch({
    control: form.control,
    name: ["countryCode", "dialCode", "phone"],
  });
  // The number a code was sent to — held so the verify call confirms that exact number.
  const [sentTo, setSentTo] = useState<PhoneFieldsValues | null>(null);
  const [otp, setOtp] = useState("");
  const [error, setError] = useState<string | null>(null);

  const canSend =
    !sendOtp.isPending && phoneFields.safeParse({ countryCode, dialCode, phone }).success;

  const onSend = form.handleSubmit(async (values) => {
    setError(null);
    try {
      // A 2xx only means the code was issued — `delivered` says whether it was actually sent,
      // and asking for a code that never left is worse than saying so.
      const undelivered = otpDeliveryError((await sendOtp.mutateAsync(values)).data);
      if (undelivered) {
        setError(undelivered);
        return;
      }
      setSentTo(values);
      setOtp("");
      toast({ title: "Code sent", description: "Enter the code sent to your phone." });
    } catch (err) {
      setError(getErrorMessage(err as Error, "Could not send code. Please try again."));
    }
  });

  const onVerify = async () => {
    if (!sentTo) return;
    setError(null);
    try {
      await verifyPhone.mutateAsync({ ...sentTo, code: otp });
      await onVerified();
      toast({ title: "Phone verified" });
    } catch (err) {
      setError(getErrorMessage(err as Error, "That code didn't match. Try again."));
    }
  };

  const onChangeNumber = () => {
    setSentTo(null);
    setOtp("");
    setError(null);
  };

  return (
    <form
      className="space-y-3 rounded-lg border border-border p-4"
      onSubmit={onSend}
      noValidate
      data-testid="verify-pay-phone-gate"
    >
      <div className="space-y-1">
        <p className="text-sm font-medium text-foreground">Verify your phone number before paying</p>
        <p className="text-sm text-muted-foreground">
          Check the number below — correct it if it&apos;s wrong — and we&apos;ll text you a code.
        </p>
      </div>

      <div className="space-y-2">
        <Label>Phone</Label>
        <PhoneInputWithCountry
          countryCode={countryCode}
          phone={phone}
          placeholder="0801 234 5678"
          disabled={!!sentTo}
          data-testid="verify-pay-phone-input"
          onChange={(next) => {
            form.setValue("countryCode", next.countryCode, { shouldValidate: true });
            form.setValue("dialCode", next.dialCode, { shouldValidate: true });
            form.setValue("phone", next.phone, { shouldValidate: true });
            setError(null);
          }}
        />
        {form.formState.errors.phone && (
          <p className="text-sm text-destructive">{form.formState.errors.phone.message}</p>
        )}
      </div>

      {!sentTo ? (
        <Button type="submit" className="w-full sm:w-auto" disabled={!canSend} data-testid="verify-pay-send-otp">
          {sendOtp.isPending ? "Sending code…" : "Send code"}
        </Button>
      ) : (
        <div className="space-y-2">
          <Label htmlFor="verify-pay-otp">Enter code</Label>
          <Input
            id="verify-pay-otp"
            inputMode="numeric"
            autoComplete="one-time-code"
            value={otp}
            onChange={(e) => setOtp(e.target.value)}
            data-testid="verify-pay-otp"
          />
          <div className="flex flex-col gap-2 sm:flex-row">
            <Button
              type="button"
              onClick={onVerify}
              disabled={verifyPhone.isPending || !otp}
              data-testid="verify-pay-verify-otp"
            >
              {verifyPhone.isPending ? "Verifying…" : "Verify phone"}
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={onChangeNumber}
              disabled={verifyPhone.isPending}
              data-testid="verify-pay-change-phone"
            >
              Change number
            </Button>
          </div>
        </div>
      )}

      {error && (
        <p className="text-sm text-destructive" role="alert" data-testid="verify-pay-phone-error">
          {error}
        </p>
      )}
    </form>
  );
}
