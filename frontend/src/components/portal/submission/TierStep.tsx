"use client";

import { getCurrencySymbol, TransactionCurrency } from "@/types/models";
import { VerificationTier } from "@/types/verification";
import { useQuoteQuery } from "@components/portal/libs/useVerificationQueries";
import { SubmissionState } from "./types";

interface Props {
  tier: VerificationTier;
  currency: TransactionCurrency;
  onChange: (patch: Partial<Pick<SubmissionState, "tier" | "currency">>) => void;
}

const TIERS: { tier: VerificationTier; title: string; blurb: string }[] = [
  { tier: VerificationTier.BASIC, title: "Basic", blurb: "Registry search" },
  { tier: VerificationTier.STANDARD, title: "Standard", blurb: "Registry + field + survey" },
  { tier: VerificationTier.PREMIUM, title: "Premium", blurb: "Standard + legal opinion" },
];

const CURRENCIES = [
  TransactionCurrency.NGN,
  TransactionCurrency.USD,
  TransactionCurrency.GBP,
  TransactionCurrency.EUR,
];

function major(minor: number): string {
  return (minor / 100).toLocaleString(undefined, { maximumFractionDigits: 2 });
}

export default function TierStep({ tier, currency, onChange }: Props) {
  const { data: quote } = useQuoteQuery(tier, currency);
  const isForeign = currency !== TransactionCurrency.NGN;

  return (
    <div className="space-y-6" data-testid="verify-new-tier">
      <div className="grid gap-3 sm:grid-cols-3">
        {TIERS.map((t) => {
          const selected = tier === t.tier;
          return (
            <button
              key={t.tier}
              type="button"
              onClick={() => onChange({ tier: t.tier })}
              className={`rounded-lg border p-4 text-left transition-colors ${
                selected ? "border-primary bg-primary/5" : "border-border hover:bg-accent"
              }`}
              data-testid={`verify-new-tier-${t.tier.toLowerCase()}`}
            >
              <span className="block font-semibold text-foreground">{t.title}</span>
              <span className="block text-xs text-muted-foreground">{t.blurb}</span>
            </button>
          );
        })}
      </div>

      <div className="flex flex-wrap gap-2">
        {CURRENCIES.map((c) => (
          <button
            key={c}
            type="button"
            onClick={() => onChange({ currency: c })}
            className={`rounded-full border px-3 py-1 text-sm ${
              currency === c ? "border-primary bg-primary/10" : "border-border"
            }`}
            data-testid={`verify-new-currency-${c.toLowerCase()}`}
          >
            {c}
          </button>
        ))}
      </div>

      {quote && (
        <div className="rounded-lg border border-border p-4">
          {(() => {
            const hasDiscount = quote.totalDiscountMinor > 0;
            const ngn = getCurrencySymbol(TransactionCurrency.NGN);
            return (
              <>
                {/* NGN is the prominent, certain, contractual figure (§4.4). */}
                <p className="text-2xl font-bold text-foreground" data-testid="verify-new-price-ngn">
                  {ngn}
                  {major(quote.netPriceNgnMinor)}
                </p>

                {/* Discount breakdown (§17.1) — auto-applied, shown as line items. */}
                {hasDiscount && (
                  <div className="mt-2 space-y-1 text-sm" data-testid="verify-new-discount">
                    <div className="flex justify-between text-muted-foreground">
                      <span>Price</span>
                      <span>{ngn}{major(quote.priceNgnMinor)}</span>
                    </div>
                    {quote.firstTimeDiscountMinor > 0 && (
                      <div className="flex justify-between text-emerald-600 dark:text-emerald-400">
                        <span>First-time discount</span>
                        <span>−{ngn}{major(quote.firstTimeDiscountMinor)}</span>
                      </div>
                    )}
                    {quote.referralCreditAppliedMinor > 0 && (
                      <div className="flex justify-between text-emerald-600 dark:text-emerald-400">
                        <span>Referral credit</span>
                        <span>−{ngn}{major(quote.referralCreditAppliedMinor)}</span>
                      </div>
                    )}
                    {quote.discountCapHit && (
                      <p className="text-xs text-muted-foreground">Maximum discount applied.</p>
                    )}
                  </div>
                )}

                {isForeign && (
                  <p className="mt-1 text-sm text-muted-foreground">
                    You&apos;ll be charged in Naira; your bank converts this — typically around{" "}
                    {getCurrencySymbol(currency)}
                    {major(quote.chargeAmountMinor)} (indicative, ±3%).
                  </p>
                )}
                <p className="mt-3 text-xs text-muted-foreground">
                  The price and rate lock for 24 hours when you continue to payment.
                </p>
              </>
            );
          })()}
        </div>
      )}
    </div>
  );
}
