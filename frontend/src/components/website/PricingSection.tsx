"use client";

import { useState } from "react";
import Link from "next/link";
import { CheckCircle2, Plus, Clock } from "lucide-react";
import { pricingTiers, currencies, formatPrice, CTA_VERIFY_HREF, type Currency } from "./home.data";

export default function PricingSection() {
  const [currency, setCurrency] = useState<Currency>("NGN");

  return (
    <section id="pricing" className="py-24 lg:py-32 bg-white">
      <div className="max-w-7xl mx-auto px-6 lg:px-8">
        {/* Header */}
        <div className="text-center mb-14">
          <div
            className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-widest mb-4"
            style={{
              backgroundColor: "rgba(63,102,83,0.08)",
              color: "var(--brand-viridian)",
              border: "1px solid rgba(63,102,83,0.15)",
            }}
          >
            Transparent Pricing
          </div>
          <h2
            className="text-4xl md:text-5xl font-extrabold editorial-spacing font-display leading-tight mb-5"
            style={{ color: "var(--brand-navy)" }}
          >
            Simple. Transparent. Certain.
          </h2>
          <p
            className="text-lg max-w-xl mx-auto"
            style={{ color: "var(--brand-on-surface-variant)" }}
          >
            Price locked at checkout. No hidden fees. No surprises. Your
            Verification ID is assigned the moment you submit.
          </p>

          {/* Currency toggle */}
          <div
            className="inline-flex items-center mt-8 p-1 rounded-xl gap-1"
            style={{
              backgroundColor: "var(--brand-surface-low)",
              border: "1px solid rgba(196,198,207,0.2)",
            }}
          >
            {currencies.map((c) => (
              <button
                key={c}
                onClick={() => setCurrency(c)}
                className="px-4 py-2 rounded-lg text-sm font-semibold transition-all duration-200"
                style={
                  currency === c
                    ? {
                        backgroundColor: "#fff",
                        color: "var(--brand-navy)",
                        boxShadow: "0 2px 8px rgba(0,13,34,0.08)",
                      }
                    : {
                        backgroundColor: "transparent",
                        color: "var(--brand-on-surface-variant)",
                      }
                }
              >
                {c}
              </button>
            ))}
          </div>

          {currency !== "NGN" && (
            <div className="mt-3 text-xs" style={{ color: "var(--brand-on-surface-variant)" }}>
              Converted from NGN · Rate for reference only · Locked at checkout
            </div>
          )}
        </div>

        {/* Tier cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-0 items-stretch">
          {pricingTiers.map((tier, idx) => {
            const isPopular = tier.popular;
            return (
              <div
                key={tier.name}
                className="relative flex flex-col p-10 transition-all duration-300"
                style={
                  isPopular
                    ? {
                        backgroundColor: "#fff",
                        borderRadius: "1rem",
                        boxShadow: "0 32px 64px -16px rgba(0,13,34,0.18), 0 0 0 1px rgba(63,102,83,0.2)",
                        zIndex: 10,
                        transform: "scale(1.04)",
                      }
                    : {
                        backgroundColor: "var(--brand-surface-low)",
                        borderRadius: idx === 0 ? "1rem 0 0 1rem" : "0 1rem 1rem 0",
                        border: "1px solid rgba(196,198,207,0.15)",
                      }
                }
              >
                {/* Most popular badge */}
                {isPopular && (
                  <div
                    className="absolute -top-4 left-1/2 -translate-x-1/2 px-4 py-1 rounded-full text-xs font-bold uppercase tracking-widest text-white"
                    style={{ background: "var(--brand-viridian)" }}
                  >
                    Most Popular
                  </div>
                )}

                {/* Tier name */}
                <div className="mb-6">
                  <h3
                    className="text-sm font-bold uppercase tracking-widest mb-1"
                    style={{
                      color: isPopular ? "var(--brand-viridian)" : "var(--brand-on-surface-variant)",
                    }}
                  >
                    {tier.name}
                  </h3>
                  <div
                    className="text-4xl font-extrabold editorial-spacing font-display"
                    style={{ color: "var(--brand-navy)" }}
                  >
                    {formatPrice(tier.priceNGN, currency)}
                  </div>
                  <div
                    className="flex items-center gap-1.5 mt-2 text-xs"
                    style={{ color: "var(--brand-on-surface-variant)" }}
                  >
                    <Clock className="w-3.5 h-3.5" />
                    {tier.sla}
                  </div>
                </div>

                <p
                  className="text-sm leading-relaxed mb-8"
                  style={{ color: "var(--brand-on-surface-variant)" }}
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
                        className="flex items-start gap-3 text-sm"
                        style={{
                          color: isEverything ? "var(--brand-navy)" : "var(--brand-on-surface-variant)",
                          fontWeight: isEverything ? 600 : 400,
                        }}
                      >
                        {isEverything ? (
                          <Plus
                            className="w-4 h-4 flex-shrink-0 mt-0.5"
                            strokeWidth={2.5}
                            style={{ color: "var(--brand-viridian)" }}
                          />
                        ) : (
                          <CheckCircle2
                            className="w-4 h-4 flex-shrink-0 mt-0.5"
                            strokeWidth={2}
                            style={{ color: "var(--brand-viridian)" }}
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
                  className="block text-center py-4 rounded-xl font-bold text-sm transition-all duration-200 hover:scale-[0.98] active:scale-95"
                  style={
                    tier.ctaStyle === "gradient"
                      ? {
                          background: "linear-gradient(135deg, var(--brand-navy) 0%, var(--brand-navy-deep) 100%)",
                          color: "#fff",
                          boxShadow: "0 6px 20px -4px rgba(0,13,34,0.35)",
                        }
                      : tier.ctaStyle === "outline-gold"
                      ? {
                          border: "2px solid rgba(115,92,0,0.4)",
                          color: "var(--brand-gold)",
                          backgroundColor: "rgba(115,92,0,0.04)",
                        }
                      : {
                          border: "1px solid rgba(196,198,207,0.5)",
                          color: "var(--brand-navy)",
                          backgroundColor: "transparent",
                        }
                  }
                >
                  {tier.cta}
                </Link>
              </div>
            );
          })}
        </div>

        {/* Trust footer */}
        <p
          className="text-center text-xs mt-10 max-w-xl mx-auto leading-relaxed"
          style={{ color: "var(--brand-on-surface-variant)" }}
        >
          All prices are exclusive of VAT. We reduce uncertainty — we do not eliminate it. Reports
          are professional opinions, not legal guarantees. First-time discount applied automatically.
        </p>
      </div>
    </section>
  );
}
