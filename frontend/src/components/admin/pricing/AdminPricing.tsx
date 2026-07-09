"use client";

import { useState } from "react";
import { Button } from "@3rdparty/ui/button";
import { Input } from "@3rdparty/ui/input";
import { Card } from "@3rdparty/ui/card";
import { toast } from "@components/3rdparty/ui/use-toast";
import { AsyncStateComponent } from "@components/ui/AsyncStateComponent";
import { usePricingQuery, useSetTierPriceMutation } from "./libs/usePricingQueries";
import { PricingTier, TierPricingView } from "@/types/pricing";
import { VerificationTier } from "@/types/verification";
import { formatMinor, humanizeEnumLabel } from "@lib/utils";

/**
 * Pricing config (§18.1, D36). Admin-editable per-tier price + itemized breakdown + the
 * derived upgrade deltas. Edits take effect on the next quote (existing 24h price locks
 * are honoured) — the Phase-18 "no deploy" exit criterion. Backend is the source of truth.
 */
export default function AdminPricing() {
  const { data, isLoading, isError } = usePricingQuery();

  return (
    <div className="mx-auto w-full max-w-3xl space-y-6 p-4 sm:p-6" data-testid="admin-pricing">
      <h1 className="text-2xl font-bold text-foreground">Pricing</h1>
      <p className="text-sm text-muted-foreground">
        Changes apply to new quotes only — customers with a live 24-hour price lock keep their locked price.
      </p>

      <AsyncStateComponent<TierPricingView> isLoading={isLoading} isError={isError} data={data}>
        {(view) => (
          <div className="space-y-4">
            {view.tiers.map((t) => (
              <TierEditor key={t.tier} tier={t} />
            ))}

            <Card className="space-y-2 p-5">
              <h2 className="text-sm font-semibold text-foreground">Upgrade deltas</h2>
              <ul className="space-y-1 text-sm">
                {view.upgradeDeltas.map((d) => (
                  <li key={`${d.fromTier}-${d.toTier}`} className="flex justify-between">
                    <span className="text-muted-foreground">{d.fromTier} → {d.toTier}</span>
                    <span className="font-medium tabular-nums">{formatMinor(d.deltaMinor)}</span>
                  </li>
                ))}
              </ul>
            </Card>
          </div>
        )}
      </AsyncStateComponent>
    </div>
  );
}

function TierEditor({ tier }: { tier: PricingTier }) {
  const [price, setPrice] = useState<string>(String((tier.priceNgnMinor ?? 0) / 100));
  const setPriceMutation = useSetTierPriceMutation();

  const onSave = async () => {
    const major = Number(price);
    if (!Number.isFinite(major) || major < 0) {
      toast({ title: "Invalid price", description: "Enter a non-negative amount.", variant: "destructive" });
      return;
    }
    await setPriceMutation.mutateAsync({ tier: tier.tier as VerificationTier, priceNgnMinor: Math.round(major * 100) });
    toast({ title: "Price updated", description: `${humanizeEnumLabel(tier.tier)} now ${formatMinor(Math.round(major * 100))}.` });
  };

  return (
    <Card className="space-y-3 p-5" data-testid={`admin-pricing-tier-${tier.tier.toLowerCase()}`}>
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-foreground">{humanizeEnumLabel(tier.tier)}</h2>
        <span className="text-xs text-muted-foreground">Current: {formatMinor(tier.priceNgnMinor)}</span>
      </div>
      <div className="flex items-end gap-3">
        <div className="flex-1">
          <label className="mb-1 block text-xs text-muted-foreground">Price (₦)</label>
          <Input
            type="number"
            min={0}
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            data-testid={`admin-pricing-input-${tier.tier.toLowerCase()}`}
          />
        </div>
        <Button onClick={onSave} disabled={setPriceMutation.isPending} data-testid={`admin-pricing-save-${tier.tier.toLowerCase()}`}>
          {setPriceMutation.isPending ? "Saving…" : "Save"}
        </Button>
      </div>
      {tier.lineItems.length > 0 && (
        <ul className="space-y-1 border-t border-border pt-2 text-sm">
          {tier.lineItems.map((li) => (
            <li key={li.id} className="flex justify-between text-muted-foreground">
              <span>{li.label}</span>
              <span className="tabular-nums">{formatMinor(li.amountMinor)}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

