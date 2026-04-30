"use client";

import { useEffect, useMemo } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@3rdparty/ui/dialog";
import { Button } from "@3rdparty/ui/button";
import VerifiedInput, { VerifiedInputType } from "@components/ui/verified_input/VerifiedInput";
import { profileCompletionSchema, type ProfileCompletionValues } from "../schemas";
import {
  RESIDENCE_COUNTRIES,
  COMMON_TIMEZONES,
  SUPPORTED_CURRENCIES,
  detectBrowserTimezone,
  suggestTimezoneForCountry,
} from "@components/website/auth/libs/auth/locale";
import { CURRENCY_NAMES, TransactionCurrency } from "@/types/models";
import { OtpChannel, AuthUser } from "@components/website/auth/models";
import {
  useCompleteProfileMutation,
  useSendOtpMutation,
  useVerifyOtpMutation,
} from "../libs/useAuthQueries";
import { AuthIntent } from "@lib/routes";
import { getErrorMessage } from "@lib/utils";

interface Props {
  open: boolean;
  user: AuthUser | undefined;
  intent: AuthIntent;
  onComplete: () => void;
}

export default function ProfileCompletionModal({ open, user, onComplete }: Props) {
  const browserTz = useMemo(() => detectBrowserTimezone(), []);
  const completeMutation = useCompleteProfileMutation();
  const sendOtp = useSendOtpMutation();
  const verifyOtp = useVerifyOtpMutation();

  // We reuse VerifiedInput which expects the verifyFormSchema shape, plus we
  // augment with country/timezone/currency. Use a single form for everything.
  // The literal `true` on emailVerified/phoneVerified satisfies the schema's
  // refinements; until the user actually verifies, the cast represents the
  // form's transient (invalid) state — submit is gated on the resolver.
  const form = useForm<ProfileCompletionValues & { email: string; emailVerified: true }>({
    resolver: zodResolver(profileCompletionSchema) as never,
    defaultValues: {
      email: user?.email ?? "",
      emailVerified: true,
      countryCode: user?.phoneCountryCode || "NG",
      dialCode: user?.phoneDialCode || "+234",
      phone: user?.phone || "",
      phoneVerified: (user?.phoneVerified ?? false) as true,
      countryOfResidence: user?.countryOfResidence || "",
      timezone: user?.timezone || browserTz,
      preferredCurrency: (user?.preferredCurrency as TransactionCurrency) || TransactionCurrency.NGN,
    },
    mode: "onBlur",
  });

  const country = form.watch("countryOfResidence");

  useEffect(() => {
    if (!country) return;
    const tz = suggestTimezoneForCountry(country, browserTz);
    if (tz && tz !== form.getValues("timezone")) {
      form.setValue("timezone", tz, { shouldValidate: true });
    }
    const c = RESIDENCE_COUNTRIES.find((rc) => rc.code === country);
    if (c) form.setValue("preferredCurrency", c.defaultCurrency, { shouldValidate: true });
  }, [country, browserTz, form]);

  const onSubmit = async (values: ProfileCompletionValues) => {
    try {
      await completeMutation.mutateAsync({
        countryCode: values.countryCode,
        dialCode: values.dialCode,
        phone: values.phone,
        countryOfResidence: values.countryOfResidence,
        timezone: values.timezone,
        preferredCurrency: values.preferredCurrency,
      });
      onComplete();
    } catch (err) {
      form.setError("root", {
        message: getErrorMessage(
          err as Error,
          "Could not save your profile. Please try again.",
        ),
      });
    }
  };

  return (
    <Dialog open={open}>
      <DialogContent showCloseButton={false} className="sm:max-w-lg max-h-[92vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-xl font-semibold">Complete your profile</DialogTitle>
        </DialogHeader>
        <p className="text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>
          We need a few more details before you can use Veriprops.
        </p>

        <form className="space-y-5 mt-4" onSubmit={form.handleSubmit(onSubmit as never)} noValidate>
          <VerifiedInput
            form={form as never}
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
                    onError(getErrorMessage(err as Error, "Could not send code.")),
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
                    onError(getErrorMessage(err as Error, "That code didn't match.")),
                },
              );
            }}
          />

          <Field label="Country of residence" error={form.formState.errors.countryOfResidence?.message}>
            <select
              {...form.register("countryOfResidence")}
              className="w-full h-11 px-3 rounded-md text-sm bg-[var(--brand-surface-card)] border border-[rgba(196,198,207,0.4)]"
            >
              <option value="">Select your country</option>
              {RESIDENCE_COUNTRIES.map((c) => (
                <option key={c.code} value={c.code}>
                  {c.flag} {c.name}
                </option>
              ))}
            </select>
          </Field>

          <Field label="Timezone" error={form.formState.errors.timezone?.message}>
            <select
              {...form.register("timezone")}
              className="w-full h-11 px-3 rounded-md text-sm bg-[var(--brand-surface-card)] border border-[rgba(196,198,207,0.4)]"
            >
              {COMMON_TIMEZONES.map((tz) => (
                <option key={tz} value={tz}>
                  {tz}
                </option>
              ))}
            </select>
          </Field>

          <Field label="Preferred currency" error={form.formState.errors.preferredCurrency?.message}>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {SUPPORTED_CURRENCIES.map((c) => {
                const selected = form.watch("preferredCurrency") === c;
                return (
                  <button
                    key={c}
                    type="button"
                    onClick={() => form.setValue("preferredCurrency", c, { shouldValidate: true })}
                    className="px-3 py-2 rounded-md text-sm font-semibold transition-all"
                    style={{
                      backgroundColor: selected ? "var(--brand-navy)" : "var(--brand-surface-card)",
                      color: selected ? "white" : "var(--brand-navy)",
                      border: selected
                        ? "1px solid var(--brand-navy)"
                        : "1px solid rgba(196,198,207,0.4)",
                    }}
                  >
                    <div>{c}</div>
                    <div
                      className="text-[10px] mt-0.5"
                      style={{
                        color: selected ? "rgba(255,255,255,0.7)" : "var(--brand-on-surface-variant)",
                      }}
                    >
                      {CURRENCY_NAMES[c]}
                    </div>
                  </button>
                );
              })}
            </div>
          </Field>

          {form.formState.errors.root && (
            <p className="text-sm" style={{ color: "var(--danger)" }}>
              {form.formState.errors.root.message}
            </p>
          )}

          <Button type="submit" className="w-full" size="lg" disabled={completeMutation.isPending}>
            {completeMutation.isPending ? "Saving…" : "Continue"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function Field({
  label,
  children,
  error,
}: {
  label: string;
  children: React.ReactNode;
  error?: string;
}) {
  return (
    <div className="space-y-1.5">
      <label className="text-sm font-semibold" style={{ color: "var(--brand-navy)" }}>
        {label}
      </label>
      {children}
      {error && (
        <p className="text-xs" style={{ color: "var(--danger)" }}>
          {error}
        </p>
      )}
    </div>
  );
}
