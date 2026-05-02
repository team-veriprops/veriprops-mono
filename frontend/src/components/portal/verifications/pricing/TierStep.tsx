"use client";

import { useMemo, useState } from "react";
import { Button } from "@3rdparty/ui/button";
import { Check, AlertCircle, AlertTriangle } from "lucide-react";
import { usePricingQuote } from "../libs/useVerificationQueries";
import type { VerificationTier } from "../libs/verification-service";

const CURRENCIES: { value: string; label: string; symbol: string }[] = [
  { value: "NGN", label: "Naira", symbol: "₦" },
  { value: "USD", label: "US Dollar", symbol: "$" },
  { value: "GBP", label: "Pound", symbol: "£" },
  { value: "EUR", label: "Euro", symbol: "€" },
];

const TIERS: {
  value: VerificationTier;
  title: string;
  blurb: string;
  sla: string;
  inclusions: string[];
  excluded: string[];
  highlight?: boolean;
}[] = [
  {
    value: "BASIC",
    title: "Basic",
    blurb: "Registry-only check.",
    sla: "3–5 business days",
    inclusions: ["Registry search", "Title authenticity"],
    excluded: ["Field inspection", "Survey assessment", "Legal opinion"],
  },
  {
    value: "STANDARD",
    title: "Standard",
    blurb: "Full ground & registry verification.",
    sla: "5–7 business days",
    inclusions: ["Registry search", "Field inspection", "Survey assessment"],
    excluded: ["Legal opinion"],
    highlight: true,
  },
  {
    value: "PREMIUM",
    title: "Premium",
    blurb: "Standard + structured legal opinion.",
    sla: "7–10 business days",
    inclusions: ["Registry search", "Field inspection", "Survey assessment", "Legal opinion"],
    excluded: [],
  },
];

interface Props {
  initial?: VerificationTier;
  pending?: boolean;
  recommendUpgrade?: boolean;
  onBack: () => void;
  onSubmit: (tier: VerificationTier, currency: string) => void;
}

export default function TierStep({
  initial = "STANDARD",
  pending,
  recommendUpgrade,
  onBack,
  onSubmit,
}: Props) {
  const [tier, setTier] = useState<VerificationTier>(initial);
  const [currency, setCurrency] = useState("NGN");
  const { data: quote } = usePricingQuote(tier, currency);

  const fmt = useMemo(() => {
    const sym = CURRENCIES.find((c) => c.value === currency)?.symbol ?? "";
    return (minor: number) => {
      const major = minor / 100;
      return `${sym}${major.toLocaleString(undefined, {
        minimumFractionDigits: currency === "NGN" ? 0 : 2,
        maximumFractionDigits: 2,
      })}`;
    };
  }, [currency]);

  return (
    <div className="space-y-6">
      <div>
        <h2
          className="text-2xl font-semibold tracking-tight"
          style={{ color: "var(--brand-navy)", fontFamily: "var(--font-display, Manrope)" }}
        >
          Choose your verification tier
        </h2>
        <p className="text-sm mt-1" style={{ color: "var(--brand-on-surface-variant)" }}>
          Pricing is locked for 24 hours once you continue to payment.
        </p>
      </div>

      {recommendUpgrade && (
        <div
          className="rounded-md p-4 flex items-start gap-3"
          style={{
            backgroundColor: "var(--brand-gold-xlight)",
            color: "var(--brand-gold)",
          }}
        >
          <AlertTriangle className="w-5 h-5 mt-0.5" />
          <div>
            <div className="font-semibold text-sm">Standard or Premium recommended</div>
            <div className="text-xs mt-1" style={{ color: "var(--brand-navy)" }}>
              You marked the C of O or survey plan as unknown. A field inspection and survey
              assessment will close that gap.
            </div>
          </div>
        </div>
      )}

      <div
        className="inline-flex rounded-lg p-1 gap-1"
        style={{ backgroundColor: "var(--brand-surface-low)" }}
      >
        {CURRENCIES.map((c) => (
          <button
            key={c.value}
            type="button"
            onClick={() => setCurrency(c.value)}
            className="text-xs font-medium px-3 py-1.5 rounded-md"
            style={{
              backgroundColor: currency === c.value ? "white" : "transparent",
              color:
                currency === c.value ? "var(--brand-navy)" : "var(--brand-on-surface-variant)",
              boxShadow: currency === c.value ? "0px 4px 12px rgba(0,13,34,0.06)" : undefined,
            }}
          >
            {c.symbol} {c.value}
          </button>
        ))}
      </div>

      {quote?.fxStale && (
        <div
          className="text-xs rounded-md p-3"
          style={{
            color: "var(--warning)",
            backgroundColor: "rgba(176,125,0,0.08)",
          }}
        >
          FX rate may be stale; the final NGN amount will lock at your provider&apos;s rate.
        </div>
      )}

      <div className="grid md:grid-cols-3 gap-4">
        {TIERS.map((t) => {
          const isOn = tier === t.value;
          const total =
            t.value === quote?.tier && currency === quote?.currency
              ? fmt(quote.totalAmountMinor)
              : "—";
          return (
            <button
              key={t.value}
              type="button"
              onClick={() => setTier(t.value)}
              className="text-left rounded-2xl p-5 transition-all"
              style={{
                backgroundColor: isOn
                  ? "var(--brand-surface-card)"
                  : "var(--brand-surface-card)",
                boxShadow: isOn
                  ? "0 0 0 2px var(--brand-viridian), 0px 24px 48px rgba(0,13,34,0.08)"
                  : "0px 12px 24px rgba(0,13,34,0.04)",
                transform: t.highlight && !isOn ? "scale(1.02)" : undefined,
                outline: t.highlight ? "1px solid rgba(63,102,83,0.18)" : undefined,
              }}
            >
              {t.highlight && (
                <span
                  className="inline-block text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full mb-2"
                  style={{
                    backgroundColor: "var(--brand-viridian-xlight)",
                    color: "var(--brand-viridian)",
                  }}
                >
                  Most popular
                </span>
              )}
              <div
                className="text-xl font-semibold"
                style={{ color: "var(--brand-navy)", fontFamily: "var(--font-display, Manrope)" }}
              >
                {t.title}
              </div>
              <div className="text-xs mt-1" style={{ color: "var(--brand-on-surface-variant)" }}>
                {t.blurb}
              </div>
              <div className="text-3xl font-semibold mt-3" style={{ color: "var(--brand-navy)" }}>
                {total}
              </div>
              <div className="text-xs mt-1" style={{ color: "var(--brand-on-surface-variant)" }}>
                {t.sla}
              </div>
              <ul className="mt-4 space-y-1.5">
                {t.inclusions.map((inc) => (
                  <li
                    key={inc}
                    className="text-xs flex items-start gap-2"
                    style={{ color: "var(--brand-on-surface)" }}
                  >
                    <Check
                      className="w-3.5 h-3.5 mt-0.5 shrink-0"
                      strokeWidth={3}
                      style={{ color: "var(--success)" }}
                    />
                    {inc}
                  </li>
                ))}
                {t.excluded.map((exc) => (
                  <li
                    key={exc}
                    className="text-xs flex items-start gap-2"
                    style={{ color: "var(--brand-outline)" }}
                  >
                    <span className="w-3.5 h-3.5 mt-0.5 shrink-0">—</span>
                    {exc}
                  </li>
                ))}
              </ul>
            </button>
          );
        })}
      </div>

      {quote && quote.tier === tier && quote.currency === currency && (
        <div
          className="rounded-xl p-5 space-y-2 text-sm"
          style={{
            backgroundColor: "var(--brand-surface-low)",
            color: "var(--brand-navy)",
          }}
        >
          <div className="text-xs font-semibold uppercase tracking-wider mb-1"
            style={{ color: "var(--brand-on-surface-variant)" }}
          >
            Line items
          </div>
          {quote.lineItems.map((li, i) => (
            <div key={i} className="flex justify-between gap-3">
              <span style={{ color: "var(--brand-on-surface)" }}>{li.label}</span>
              <span className="font-medium tabular-nums">{fmt(li.amountMinor)}</span>
            </div>
          ))}
          <div className="flex justify-between pt-2 border-t" style={{ borderColor: "var(--brand-surface-high)" }}>
            <span className="font-semibold">Total</span>
            <span className="font-semibold tabular-nums">{fmt(quote.totalAmountMinor)}</span>
          </div>
          {quote.fxRate && (
            <div className="text-[11px]" style={{ color: "var(--brand-on-surface-variant)" }}>
              FX: 1 NGN = {quote.fxRate.toFixed(6)} {currency}
            </div>
          )}
        </div>
      )}

      <div className="flex justify-between pt-2">
        <Button type="button" variant="outline" onClick={onBack}>
          Back
        </Button>
        <Button type="button" disabled={pending} onClick={() => onSubmit(tier, currency)}>
          {pending ? "Locking…" : "Continue to consents"}
        </Button>
      </div>
    </div>
  );
}
