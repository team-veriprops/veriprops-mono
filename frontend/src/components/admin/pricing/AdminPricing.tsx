"use client";

import { useRef, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@3rdparty/ui/button";
import { Input } from "@3rdparty/ui/input";
import { Card } from "@3rdparty/ui/card";
import { toast } from "sonner";
import { AsyncStateComponent } from "@components/ui/AsyncStateComponent";
import { usePricingQuery, useSetTierPricingMutation } from "./libs/usePricingQueries";
import { PricingTier, TierPricingView } from "@/types/pricing";
import { VerificationTier } from "@/types/verification";
import { cn, formatMinor, humanizeEnumLabel, majorToMinor, minorToMajorText } from "@lib/utils";
import { getErrorMessage } from "@lib/errors";

/**
 * Pricing config (§18.1, D36). Admin-editable per-tier price + itemized breakdown (saved together) + the
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
                    <span className="text-muted-foreground">
                      {humanizeEnumLabel(d.fromTier)} → {humanizeEnumLabel(d.toTier)}
                    </span>
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

/** One editable breakdown row; `key` is a client-only React key, never sent. */
interface DraftItem {
  key: number;
  label: string;
  amount: string; // naira, as typed
}

/**
 * A tier's price and its itemised breakdown, edited and saved together: the backend refuses
 * items that don't add up to the price, and a price the commission margin can't meet.
 */
function TierEditor({ tier }: { tier: PricingTier }) {
  const slug = tier.tier.toLowerCase();
  const nextKey = useRef(tier.lineItems.length);
  const [price, setPrice] = useState(() => minorToMajorText(tier.priceNgnMinor));
  const [items, setItems] = useState<DraftItem[]>(() =>
    tier.lineItems.map((li, i) => ({ key: i, label: li.label, amount: minorToMajorText(li.amountMinor) })),
  );
  const save = useSetTierPricingMutation();

  const priceMinor = majorToMinor(price);
  const itemMinors = items.map((it) => majorToMinor(it.amount));
  // Input feedback only — the backend enforces the sum. Shown once every amount reads.
  const itemsTotal = itemMinors.every((m) => m !== undefined)
    ? itemMinors.reduce<number>((sum, m) => sum + (m ?? 0), 0)
    : undefined;

  const updateItem = (key: number, patch: Partial<DraftItem>) =>
    setItems((rows) => rows.map((row) => (row.key === key ? { ...row, ...patch } : row)));
  const addItem = () => setItems((rows) => [...rows, { key: nextKey.current++, label: "", amount: "" }]);
  const removeItem = (key: number) => setItems((rows) => rows.filter((row) => row.key !== key));

  const onSave = async () => {
    if (priceMinor === undefined) {
      toast.error("Invalid price", { description: "Enter the price in naira." });
      return;
    }
    if (items.some((it) => !it.label.trim()) || itemsTotal === undefined) {
      toast.error("Incomplete breakdown", { description: "Give every line item a label and an amount in naira." });
      return;
    }
    const lineItems = items.map((it, i) => ({ label: it.label.trim(), amountMinor: itemMinors[i] as number }));
    try {
      await save.mutateAsync({ tier: tier.tier as VerificationTier, priceNgnMinor: priceMinor, lineItems });
    } catch (err) {
      // A refusal (a price that leaves the agent commissions below the minimum margin, or items
      // that don't add up) is shown in the backend's words; getErrorMessage keeps a 5xx's text
      // off the screen.
      toast.error(getErrorMessage(err, "Could not update the price."));
      return;
    }
    toast.success("Price updated", { description: `${humanizeEnumLabel(tier.tier)} now ${formatMinor(priceMinor)}.` });
  };

  return (
    <Card className="space-y-3 p-5" data-testid={`admin-pricing-tier-${slug}`}>
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-foreground">{humanizeEnumLabel(tier.tier)}</h2>
        <span className="text-xs text-muted-foreground">Current: {formatMinor(tier.priceNgnMinor)}</span>
      </div>
      <div>
        <label htmlFor={`admin-pricing-input-${slug}`} className="mb-1 block text-xs text-muted-foreground">
          Price (₦)
        </label>
        <Input
          id={`admin-pricing-input-${slug}`}
          inputMode="decimal"
          value={price}
          onChange={(e) => setPrice(e.target.value)}
          data-testid={`admin-pricing-input-${slug}`}
        />
      </div>

      <fieldset className="space-y-2 border-t border-border pt-3">
        <legend className="text-xs font-medium text-muted-foreground">
          Breakdown shown to customers {items.length === 0 && "(none)"}
        </legend>
        {items.map((it, i) => (
          <div key={it.key} className="flex flex-wrap items-center gap-2 sm:flex-nowrap">
            <Input
              className="min-w-0 flex-1 basis-full sm:basis-auto"
              placeholder="Label"
              aria-label={`Line item ${i + 1} label`}
              value={it.label}
              onChange={(e) => updateItem(it.key, { label: e.target.value })}
              data-testid={`admin-pricing-item-label-${slug}-${i}`}
            />
            <Input
              className="w-32 flex-1 sm:flex-none"
              inputMode="decimal"
              placeholder="₦"
              aria-label={`Line item ${i + 1} amount in naira`}
              value={it.amount}
              onChange={(e) => updateItem(it.key, { amount: e.target.value })}
              data-testid={`admin-pricing-item-amount-${slug}-${i}`}
            />
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label={`Remove line item ${i + 1}`}
              onClick={() => removeItem(it.key)}
              data-testid={`admin-pricing-item-remove-${slug}-${i}`}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        ))}
        <div className="flex flex-wrap items-center justify-between gap-2">
          <Button type="button" variant="outline" size="sm" onClick={addItem} data-testid={`admin-pricing-item-add-${slug}`}>
            <Plus className="mr-1 h-4 w-4" /> Add line item
          </Button>
          {items.length > 0 && (
            <span
              className={cn(
                "text-xs tabular-nums",
                itemsTotal !== undefined && itemsTotal === priceMinor ? "text-muted-foreground" : "text-destructive",
              )}
              data-testid={`admin-pricing-items-total-${slug}`}
            >
              Items total {itemsTotal === undefined ? "—" : formatMinor(itemsTotal)} · must equal the price
            </span>
          )}
        </div>
      </fieldset>

      <div className="flex justify-end">
        <Button onClick={onSave} disabled={save.isPending} data-testid={`admin-pricing-save-${slug}`}>
          {save.isPending ? "Saving…" : "Save"}
        </Button>
      </div>
    </Card>
  );
}

