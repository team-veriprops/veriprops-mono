"use client";

import { useState } from "react";
import Link from "next/link";
import { CheckCircle2, Plus, Clock } from "lucide-react";
import { currencies, formatPrice, withLivePrices, CTA_VERIFY_HREF, type Currency } from "./home.data";
import type { PublicPricingTier } from "@/types/models";
import { cn } from "@lib/utils";

interface PricingSectionProps {
  /** Live tier prices from the backend's public config, fetched by the server page so the
   * server HTML and the hydrated client render the same figures. A tier without one shows no
   * figure — the backend is the only source of prices. */
  prices: PublicPricingTier[];
}

export default function PricingSection({ prices }: PricingSectionProps) {
  const [currency, setCurrency] = useState<Currency>("NGN");

  const resolvedTiers = withLivePrices(prices);

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
                  {tier.priceNGN != null && (
                    <div
                      className="text-4xl font-extrabold editorial-spacing font-display text-brand-navy"
                    >
                      {formatPrice(tier.priceNGN, currency)}
                    </div>
                  )}
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
