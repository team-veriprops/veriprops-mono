"use client";

import { useEffect, useMemo } from "react";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@3rdparty/ui/dialog";
import { Button } from "@3rdparty/ui/button";
import VerifiedInput, { VerifiedInputType } from "@components/ui/verified_input/VerifiedInput";
import PhoneInputWithCountry from "@components/ui/form/PhoneInputWithCountry";
import { profileCompletionSchema, type ProfileCompletionValues } from "../schemas";
import {
  RESIDENCE_COUNTRIES,
  COMMON_TIMEZONES,
  SUPPORTED_CURRENCIES,
  detectBrowserTimezone,
  suggestTimezoneForCountry,
} from "@components/website/auth/libs/auth/locale";
import { CURRENCY_NAMES, TransactionCurrency } from "@/types/models";
import { OtpChannel, AuthUser, AuthIntent } from "@components/website/auth/models";
import {
  useCompleteProfileMutation,
  useSendOtpMutation,
  useVerifyOtpMutation,
  usePublicConfigQuery,
} from "../libs/useAuthQueries";
import { getErrorMessage, cn } from "@lib/utils";
import { DEFAULT_DIAL_CODE } from "@lib/config/app";

interface Props {
  open: boolean;
  user: AuthUser | undefined;
  intent: AuthIntent;
  onComplete: () => void;
}

// Mirrors the `phone` field constraints in verifyFormSchema. Also rejects the
// synthetic placeholder AuthService.find_or_create_oauth_user seeds new OAuth
// signups with ("0000000000") — it's shaped like a valid number, so it must
// be excluded explicitly or a user could complete their profile without ever
// entering a real one.
const OAUTH_PLACEHOLDER_PHONE = "0000000000";
const isValidPhoneNumber = (phone: string) =>
  /^\d{7,15}$/.test(phone) && phone !== OAUTH_PLACEHOLDER_PHONE;

export default function ProfileCompletionModal({ open, user, onComplete }: Props) {
  const browserTz = useMemo(() => detectBrowserTimezone(), []);
  const completeMutation = useCompleteProfileMutation();
  const sendOtp = useSendOtpMutation();
  const verifyOtp = useVerifyOtpMutation();
  const { data: publicConfig } = usePublicConfigQuery();
  const phoneVerificationEnabled = publicConfig?.phoneVerificationEnabled ?? true;

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
      dialCode: user?.phoneDialCode || DEFAULT_DIAL_CODE,
      phone: user?.phone || "",
      phoneVerified: (user?.phoneVerified ?? false) as true,
      countryOfResidence: user?.countryOfResidence || "",
      timezone: user?.timezone || browserTz,
      preferredCurrency: (user?.preferredCurrency as TransactionCurrency) || TransactionCurrency.NGN,
    },
    mode: "onBlur",
  });

  const country = useWatch({ control: form.control, name: "countryOfResidence" });
  const preferredCurrency = useWatch({ control: form.control, name: "preferredCurrency" });
  const phone = useWatch({ control: form.control, name: "phone" });
  const phoneCountryCode = useWatch({ control: form.control, name: "countryCode" });

  // Phone is always required, whether or not it needs to be OTP-verified here.
  // When verification is off, the number is still collected — so we satisfy
  // the "verified" refine only once the number itself passes its own
  // validation, rather than unconditionally, so a placeholder/blank value
  // (e.g. the OAuth signup placeholder) can't slip through unedited.
  useEffect(() => {
    if (!phoneVerificationEnabled) {
      form.setValue("phoneVerified", isValidPhoneNumber(phone) as never, { shouldValidate: true });
    }
  }, [phoneVerificationEnabled, phone, form]);

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
      <DialogContent
        showCloseButton={false}
        preventOutsideClose
        className="sm:max-w-lg max-h-[92vh] overflow-y-auto"
      >
        <DialogHeader>
          <DialogTitle className="text-xl font-semibold">Complete your profile</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-brand-on-surface-variant">
          We need a few more details before you can use Veriprops.
        </p>

        <form className="space-y-5 mt-4" onSubmit={form.handleSubmit(onSubmit as never)} noValidate>
          {phoneVerificationEnabled ? (
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
          ) : (
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">
                Phone <span className="text-destructive">*</span>
              </label>
              <PhoneInputWithCountry
                countryCode={phoneCountryCode}
                phone={phone}
                onChange={({ countryCode, dialCode, phone }) => {
                  form.setValue("countryCode", countryCode, { shouldValidate: true });
                  form.setValue("dialCode", dialCode, { shouldValidate: true });
                  form.setValue("phone", phone, { shouldValidate: true });
                }}
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

          <Field label="Country of residence" error={form.formState.errors.countryOfResidence?.message}>
            <select
              {...form.register("countryOfResidence")}
              className="w-full h-11 px-3 rounded-md text-sm bg-brand-surface-card border border-brand-outline-variant/40"
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
              className="w-full h-11 px-3 rounded-md text-sm bg-brand-surface-card border border-brand-outline-variant/40"
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
                const selected = preferredCurrency === c;
                return (
                  <button
                    key={c}
                    type="button"
                    onClick={() => form.setValue("preferredCurrency", c, { shouldValidate: true })}
                    className={cn(
                      "px-3 py-2 rounded-md text-sm font-semibold transition-all",
                      selected
                        ? "bg-brand-navy text-white border border-brand-navy"
                        : "bg-brand-surface-card text-brand-navy border border-brand-outline-variant/40"
                    )}
                  >
                    <div>{c}</div>
                    <div
                      className={cn(
                        "text-[10px] mt-0.5",
                        selected ? "text-white/70" : "text-brand-on-surface-variant"
                      )}
                    >
                      {CURRENCY_NAMES[c]}
                    </div>
                  </button>
                );
              })}
            </div>
          </Field>

          {form.formState.errors.root && (
            <p className="text-sm text-danger">
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
      <label className="text-sm font-semibold text-brand-navy">
        {label}
      </label>
      {children}
      {error && (
        <p className="text-xs text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
