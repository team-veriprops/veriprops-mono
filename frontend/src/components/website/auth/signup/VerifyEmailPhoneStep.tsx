"use client";

import { useEffect } from "react";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Button } from "@3rdparty/ui/button";
import VerifiedInput, { VerifiedInputType } from "@components/ui/verified_input/VerifiedInput";
import PhoneInputWithCountry from "@components/ui/form/PhoneInputWithCountry";
import { verifyFormSchema, type VerifyFormValues } from "@components/ui/verified_input/schemas";
import { useSendOtpMutation, useVerifyOtpMutation, usePublicConfigQuery } from "../libs/useAuthQueries";
import { OtpChannel } from "@components/website/auth/models";
import { getErrorMessage } from "@lib/utils";
import { DEFAULT_DIAL_CODE } from "@lib/config/app";

export type VerifyStepValues = VerifyFormValues;

// Mirrors the `phone` field constraints in verifyFormSchema.
const isValidPhoneNumber = (phone: string) => /^\d{7,15}$/.test(phone);

interface Props {
  defaults: { email: string; countryCode?: string; dialCode?: string; phone?: string };
  onSubmit: (values: VerifyStepValues) => void;
  onBack: () => void;
}

export default function VerifyEmailPhoneStep({ defaults, onSubmit, onBack }: Props) {
  const { data: publicConfig } = usePublicConfigQuery();
  // Default on while the flag loads so we never silently drop a required check.
  const phoneVerificationEnabled = publicConfig?.phoneVerificationEnabled ?? true;

  const form = useForm<VerifyFormValues>({
    resolver: zodResolver(verifyFormSchema),
    defaultValues: {
      email: defaults.email,
      countryCode: defaults.countryCode ?? "NG",
      dialCode: defaults.dialCode ?? DEFAULT_DIAL_CODE,
      phone: defaults.phone ?? "",
      emailVerified: false,
      phoneVerified: false,
    },
    mode: "onBlur",
  });

  const sendOtp = useSendOtpMutation();
  const verifyOtp = useVerifyOtpMutation();
  const emailVerified = useWatch({ control: form.control, name: "emailVerified" });
  const phoneVerified = useWatch({ control: form.control, name: "phoneVerified" });
  const phone = useWatch({ control: form.control, name: "phone" });

  // Phone is always required, whether or not it needs to be OTP-verified here.
  // When verification is off, the number is still collected (and verified
  // later, at payment) — so we satisfy the "verified" refine only once the
  // number itself passes its own validation, rather than unconditionally on
  // mount, so the Continue button doesn't enable before a phone is entered.
  useEffect(() => {
    if (!phoneVerificationEnabled) {
      form.setValue("phoneVerified", isValidPhoneNumber(phone), { shouldValidate: true });
    }
  }, [phoneVerificationEnabled, phone, form]);

  return (
    <form className="space-y-6" onSubmit={form.handleSubmit(onSubmit)} noValidate data-testid="verify-form">
      <p
        className="text-sm leading-relaxed"
        style={{ color: "var(--brand-on-surface-variant)" }}
      >
        {phoneVerificationEnabled
          ? "We need to confirm both your email and phone number. We'll send a 6-digit code to each."
          : "We need to confirm your email. We'll send a 6-digit code."}
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

      {phoneVerificationEnabled ? (
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
      ) : (
        <div className="space-y-2">
          <label className="text-sm font-medium text-foreground">
            Phone <span className="text-destructive">*</span>
          </label>
          <PhoneInputWithCountry
            form={form}
            isVerified={false}
            onChanged={() => {}}
            placeholder="0801 234 5678"
          />
          {(form.formState.touchedFields.phone || form.formState.isSubmitted) &&
            (form.formState.errors.phone || form.formState.errors.phoneVerified) && (
            <p className="text-sm text-destructive">
              {form.formState.errors.phone?.message ?? "Please enter your phone number"}
            </p>
          )}
        </div>
      )}

      <div className="flex gap-3 pt-2">
        <Button type="button" variant="outline" className="flex-1" onClick={onBack} size="lg" data-testid="verify-back">
          Back
        </Button>
        <Button
          type="submit"
          className="flex-1"
          size="lg"
          disabled={!emailVerified || !phoneVerified}
          data-testid="verify-submit"
        >
          Continue
        </Button>
      </div>
    </form>
  );
}
