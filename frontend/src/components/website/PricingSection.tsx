"use client";

import { useState } from "react";
import Link from "next/link";
import { CheckCircle2, Plus, Clock } from "lucide-react";
import { pricingTiers, currencies, formatPrice, CTA_VERIFY_HREF, type Currency } from "./home.data";
import { usePublicConfigQuery } from "./auth/libs/useAuthQueries";
import { VerificationTier } from "@/types/verification";
import { cn } from "@lib/utils";

// Maps the static marketing tier name onto the backend tier enum so a live
// pricing_config price can be merged in; falls back per-tier to the static
// home.data.ts figure when the backend price is unavailable for that tier.
const TIER_ENUM_BY_NAME: Record<string, VerificationTier> = {
  Basic: VerificationTier.BASIC,
  Standard: VerificationTier.STANDARD,
  Premium: VerificationTier.PREMIUM,
};

export default function PricingSection() {
  const [currency, setCurrency] = useState<Currency>("NGN");
  const { data: publicConfig } = usePublicConfigQuery();

  const resolvedTiers = pricingTiers.map((tier) => {
    const backendMinor = publicConfig?.pricingTiers?.find(
      (t) => t.tier === TIER_ENUM_BY_NAME[tier.name]
    )?.priceNgnMinor;
    // Backend price is in kobo (minor units); home.data.ts prices are whole naira.
    return backendMinor != null ? { ...tier, priceNGN: backendMinor / 100 } : tier;
  });

  return (
    <section id="pricing" className="py-24 lg:py-32 bg-white">
      <div className="max-w-7xl mx-auto px-6 lg:px-8">
        {/* Header */}
        <div className="text-center mb-14">
          <div
            className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-widest mb-4 bg-brand-viridian/8 text-brand-viridian border border-brand-viridian/15"
          >
            Transparent Pricing
          </div>
          <h2
            className="text-4xl md:text-5xl font-extrabold editorial-spacing font-display leading-tight mb-5 text-brand-navy"
          >
            Simple. Transparent. Certain.
          </h2>
          <p
            className="text-lg max-w-xl mx-auto text-brand-on-surface-variant"
          >
            Price locked at checkout. No hidden fees. No surprises. Your
            Verification ID is assigned the moment you submit.
          </p>

          {/* Currency toggle */}
          <div
            className="inline-flex items-center mt-8 p-1 rounded-xl gap-1 bg-brand-surface-low border border-brand-outline-variant/20"
          >
            {currencies.map((c) => (
              <button
                key={c}
                onClick={() => setCurrency(c)}
                className={cn(
                  "px-4 py-2 rounded-lg text-sm font-semibold transition-all duration-200",
                  currency === c
                    ? "bg-white text-brand-navy shadow-[0_2px_8px_rgba(0,13,34,0.08)]"
                    : "bg-transparent text-brand-on-surface-variant"
                )}
              >
                {c}
              </button>
            ))}
          </div>

          {currency !== "NGN" && (
            <div className="mt-3 text-xs text-brand-on-surface-variant">
              Converted from NGN · Rate for reference only · Locked at checkout
            </div>
          )}
        </div>

        {/* Tier cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-0 items-stretch">
          {resolvedTiers.map((tier, idx) => {
            const isPopular = tier.popular;
            return (
              <div
                key={tier.name}
                className={cn(
                  "relative flex flex-col p-10 transition-all duration-300",
                  isPopular
                    ? "bg-white rounded-2xl shadow-[0_32px_64px_-16px_rgba(0,13,34,0.18),0_0_0_1px_rgba(63,102,83,0.2)] z-10 scale-[1.04]"
                    : cn(
                        "bg-brand-surface-low border border-brand-outline-variant/15",
                        idx === 0 ? "rounded-l-2xl" : "rounded-r-2xl"
                      )
                )}
              >
                {/* Most popular badge */}
                {isPopular && (
                  <div
                    className="absolute -top-4 left-1/2 -translate-x-1/2 px-4 py-1 rounded-full text-xs font-bold uppercase tracking-widest text-white bg-brand-viridian"
                  >
                    Most Popular
                  </div>
                )}

                {/* Tier name */}
                <div className="mb-6">
                  <h3
                    className={cn(
                      "text-sm font-bold uppercase tracking-widest mb-1",
                      isPopular ? "text-brand-viridian" : "text-brand-on-surface-variant"
                    )}
                  >
                    {tier.name}
                  </h3>
                  <div
                    className="text-4xl font-extrabold editorial-spacing font-display text-brand-navy"
                  >
                    {formatPrice(tier.priceNGN, currency)}
                  </div>
                  <div
                    className="flex items-center gap-1.5 mt-2 text-xs text-brand-on-surface-variant"
                  >
                    <Clock className="w-3.5 h-3.5" />
                    {tier.sla}
                  </div>
                </div>

                <p
                  className="text-sm leading-relaxed mb-8 text-brand-on-surface-variant"
                >
                  {tier.description}
                </p>

                {/* Feature list */}
                <ul className="space-y-3 flex-1 mb-10">
                  {tier.features.map((feature) => {
                    const isEverything = feature.startsWith("Everything");
                    return (
                      <li
                        key={feature}
                        className={cn(
                          "flex items-start gap-3 text-sm",
                          isEverything ? "text-brand-navy font-semibold" : "text-brand-on-surface-variant font-normal"
                        )}
                      >
                        {isEverything ? (
                          <Plus
                            className="w-4 h-4 shrink-0 mt-0.5 text-brand-viridian"
                            strokeWidth={2.5}
                          />
                        ) : (
                          <CheckCircle2
                            className="w-4 h-4 shrink-0 mt-0.5 text-brand-viridian"
                            strokeWidth={2}
                          />
                        )}
                        {feature}
                      </li>
                    );
                  })}
                </ul>

                {/* CTA button */}
                <Link
                  href={`${CTA_VERIFY_HREF}&tier=${tier.name.toLowerCase()}`}
                  className={cn(
                    "block text-center py-4 rounded-xl font-bold text-sm transition-all duration-200 hover:scale-[0.98] active:scale-95",
                    tier.ctaStyle === "gradient"
                      ? "signature-gradient text-white shadow-[0_6px_20px_-4px_rgba(0,13,34,0.35)]"
                      : tier.ctaStyle === "outline-gold"
                      ? "border-2 border-brand-gold/40 text-brand-gold bg-brand-gold/4"
                      : "border border-brand-outline-variant/50 text-brand-navy bg-transparent"
                  )}
                >
                  {tier.cta}
                </Link>
              </div>
            );
          })}
        </div>

        {/* Trust footer */}
        <p
          className="text-center text-xs mt-10 max-w-xl mx-auto leading-relaxed text-brand-on-surface-variant"
        >
          All prices are exclusive of VAT. We reduce uncertainty — we do not eliminate it. Reports
          are professional opinions, not legal guarantees. First-time discount applied automatically.
        </p>
      </div>
    </section>
  );
}
