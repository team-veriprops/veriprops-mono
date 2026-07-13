"use client";

import { useEffect, useMemo } from "react";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Button } from "@3rdparty/ui/button";
import { signupStep3Schema, type SignupStep3Values } from "../schemas";
import {
  RESIDENCE_COUNTRIES,
  COMMON_TIMEZONES,
  SUPPORTED_CURRENCIES,
  detectBrowserTimezone,
  suggestTimezoneForCountry,
} from "@components/website/auth/libs/auth/locale";
import { CURRENCY_NAMES, TransactionCurrency } from "@/types/models";
import { cn } from "@lib/utils";

interface Props {
  defaultValues?: Partial<SignupStep3Values>;
  onSubmit: (values: SignupStep3Values) => void;
  onBack: () => void;
}

export default function ResidenceStep({ defaultValues, onSubmit, onBack }: Props) {
  const browserTz = useMemo(() => detectBrowserTimezone(), []);
  const form = useForm<SignupStep3Values>({
    resolver: zodResolver(signupStep3Schema),
    defaultValues: {
      countryOfResidence: defaultValues?.countryOfResidence ?? "",
      timezone: defaultValues?.timezone ?? browserTz,
      preferredCurrency:
        defaultValues?.preferredCurrency ?? TransactionCurrency.NGN,
    },
    mode: "onBlur",
  });

  const country = useWatch({ control: form.control, name: "countryOfResidence" });
  const preferredCurrency = useWatch({ control: form.control, name: "preferredCurrency" });

  useEffect(() => {
    if (!country) return;
    const tz = suggestTimezoneForCountry(country, browserTz);
    if (tz && tz !== form.getValues("timezone")) {
      form.setValue("timezone", tz, { shouldValidate: true });
    }
    const c = RESIDENCE_COUNTRIES.find((rc) => rc.code === country);
    if (c) {
      form.setValue("preferredCurrency", c.defaultCurrency, { shouldValidate: true });
    }
  }, [country, browserTz, form]);

  return (
    <form className="space-y-5" onSubmit={form.handleSubmit(onSubmit)} noValidate>
      <p className="text-sm leading-relaxed text-brand-on-surface-variant">
        Tells us where you are so we can show prices in your currency and time things in your timezone.
      </p>

      <Field label="Country of residence" error={form.formState.errors.countryOfResidence?.message}>
        <select
          {...form.register("countryOfResidence")}
          className="w-full h-11 px-3 rounded-md text-sm bg-brand-surface-card border border-brand-outline-variant/40 focus:outline-none focus:ring-2 focus:ring-ring"
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
          className="w-full h-11 px-3 rounded-md text-sm bg-brand-surface-card border border-brand-outline-variant/40 focus:outline-none focus:ring-2 focus:ring-ring"
        >
          {COMMON_TIMEZONES.map((tz) => (
            <option key={tz} value={tz}>
              {tz}
            </option>
          ))}
        </select>
        <p className="text-xs mt-1 text-brand-on-surface-variant">
          Auto-suggested from your country. Adjust if needed.
        </p>
      </Field>

      <Field label="Preferred currency" error={form.formState.errors.preferredCurrency?.message}>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {SUPPORTED_CURRENCIES.map((c) => {
            const selected = preferredCurrency === c;
            return (
              <button
                key={c}
                type="button"
                onClick={() =>
                  form.setValue("preferredCurrency", c, { shouldValidate: true })
                }
                className={cn(
                  "px-3 py-2.5 rounded-md text-sm font-semibold transition-all duration-150",
                  selected
                    ? "bg-brand-navy text-white border border-brand-navy shadow-[0_4px_12px_-3px_rgba(0,13,34,0.18)]"
                    : "bg-brand-surface-card text-brand-navy border border-brand-outline-variant/40"
                )}
              >
                <div>{c}</div>
                <div
                  className={cn(
                    "text-[10px] font-medium mt-0.5",
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

      <div className="flex gap-3 pt-2">
        <Button type="button" variant="outline" className="flex-1" onClick={onBack} size="lg">
          Back
        </Button>
        <Button type="submit" className="flex-1" size="lg">
          Continue
        </Button>
      </div>
    </form>
  );
}

function Field({ label, children, error }: { label: string; children: React.ReactNode; error?: string }) {
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
