"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Button } from "@3rdparty/ui/button";
import VerifiedInput, { VerifiedInputType } from "@components/ui/verified_input/VerifiedInput";
import { verifyFormSchema, type VerifyFormValues } from "@components/ui/verified_input/schemas";
import { useSendOtpMutation, useVerifyOtpMutation } from "../libs/useAuthQueries";
import { OtpChannel } from "@components/website/auth/models";
import { getErrorMessage } from "@lib/utils";

export interface VerifyStepValues extends VerifyFormValues {}

interface Props {
  defaults: { email: string; countryCode?: string; dialCode?: string; phone?: string };
  onSubmit: (values: VerifyStepValues) => void;
  onBack: () => void;
}

export default function VerifyEmailPhoneStep({ defaults, onSubmit, onBack }: Props) {
  const form = useForm<VerifyFormValues>({
    resolver: zodResolver(verifyFormSchema),
    defaultValues: {
      email: defaults.email,
      countryCode: defaults.countryCode ?? "NG",
      dialCode: defaults.dialCode ?? "+234",
      phone: defaults.phone ?? "",
      emailVerified: false,
      phoneVerified: false,
    },
    mode: "onBlur",
  });

  const sendOtp = useSendOtpMutation();
  const verifyOtp = useVerifyOtpMutation();

  return (
    <form className="space-y-6" onSubmit={form.handleSubmit(onSubmit)} noValidate>
      <p
        className="text-sm leading-relaxed"
        style={{ color: "var(--brand-on-surface-variant)" }}
      >
        We need to confirm both your email and phone number. We&apos;ll send a 6-digit code to each.
      </p>

      <VerifiedInput
        form={form}
        field="email"
        label="Email"
        type={VerifiedInputType.EMAIL}
        placeholder="you@example.com"
        inputType="email"
        onSendVerificationMessage={({ onSuccess, onError }) => {
          sendOtp.mutate(
            { channel: OtpChannel.EMAIL, email: form.getValues("email") },
            {
              onSuccess: () => onSuccess(),
              onError: (err) =>
                onError(getErrorMessage(err as Error, "Could not send code. Please try again.")),
            },
          );
        }}
        onValidateVerificationOtp={({ otp, onSuccess, onError }) => {
          verifyOtp.mutate(
            { channel: OtpChannel.EMAIL, email: form.getValues("email"), code: otp ?? "" },
            {
              onSuccess: () => onSuccess(),
              onError: (err) =>
                onError(getErrorMessage(err as Error, "That code didn't match. Try again.")),
            },
          );
        }}
      />

      <VerifiedInput
        form={form}
        field="phone"
        label="Phone"
        type={VerifiedInputType.PHONE}
        placeholder="0801 234 5678"
        onSendVerificationMessage={({ onSuccess, onError }) => {
          const v = form.getValues();
          sendOtp.mutate(
            {
              channel: OtpChannel.PHONE,
              countryCode: v.countryCode,
              dialCode: v.dialCode,
              phone: v.phone,
            },
            {
              onSuccess: () => onSuccess(),
              onError: (err) =>
                onError(getErrorMessage(err as Error, "Could not send code. Please try again.")),
            },
          );
        }}
        onValidateVerificationOtp={({ otp, onSuccess, onError }) => {
          const v = form.getValues();
          verifyOtp.mutate(
            {
              channel: OtpChannel.PHONE,
              countryCode: v.countryCode,
              dialCode: v.dialCode,
              phone: v.phone,
              code: otp ?? "",
            },
            {
              onSuccess: () => onSuccess(),
              onError: (err) =>
                onError(getErrorMessage(err as Error, "That code didn't match. Try again.")),
            },
          );
        }}
      />

      <div className="flex gap-3 pt-2">
        <Button type="button" variant="outline" className="flex-1" onClick={onBack} size="lg">
          Back
        </Button>
        <Button
          type="submit"
          className="flex-1"
          size="lg"
          disabled={!form.watch("emailVerified") || !form.watch("phoneVerified")}
        >
          Continue
        </Button>
      </div>
    </form>
  );
}
