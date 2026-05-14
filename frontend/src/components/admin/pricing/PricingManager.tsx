"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, Save, Plus, Trash2 } from "lucide-react";
import {
  usePricingTiers,
  useUpsertPricingTierMutation,
} from "@components/admin/libs/useAdminQueries";
import type { PricingTierConfigDto, UpsertPricingTierPayload } from "@components/admin/libs/admin-service";

function formatMinor(minor: number) {
  return `₦${(minor / 100).toLocaleString("en-NG", { minimumFractionDigits: 0 })}`;
}

interface TierEditorProps {
  config: PricingTierConfigDto;
}

function TierEditor({ config }: TierEditorProps) {
  const [open, setOpen] = useState(false);
  const [label, setLabel] = useState(config.label);
  const [serviceFee, setServiceFee] = useState(String(config.serviceFeeMinor));
  const [lineItems, setLineItems] = useState(
    config.lineItems.map((li) => ({
      label: li.label,
      amountMinor: String(li.amountMinor),
      description: li.description ?? "",
      sortOrder: li.sortOrder,
    })),
  );

  const upsert = useUpsertPricingTierMutation();

  function addLineItem() {
    setLineItems((prev) => [
      ...prev,
      { label: "", amountMinor: "0", description: "", sortOrder: prev.length },
    ]);
  }

  function removeLineItem(i: number) {
    setLineItems((prev) => prev.filter((_, idx) => idx !== i));
  }

  async function save() {
    const payload: UpsertPricingTierPayload = {
      tier: config.tier,
      label,
      currency: config.currency,
      serviceFeeMinor: parseInt(serviceFee, 10) || 0,
      lineItems: lineItems.map((li, i) => ({
        label: li.label,
        amountMinor: parseInt(li.amountMinor, 10) || 0,
        description: li.description || undefined,
        sortOrder: i,
      })),
    };
    await upsert.mutateAsync(payload);
  }

  return (
    <div
      className="rounded-xl overflow-hidden"
      style={{ border: "1px solid rgba(196,198,207,0.25)", background: "#fff" }}
    >
      <button
        type="button"
        className="w-full flex items-center justify-between px-5 py-4 text-left"
        onClick={() => setOpen((v) => !v)}
      >
        <div>
          <span className="font-semibold" style={{ color: "var(--brand-navy)" }}>
            {config.tier}
          </span>
          <span className="ml-3 text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>
            {config.currency} · Service fee: {formatMinor(config.serviceFeeMinor)}
          </span>
        </div>
        {open ? (
          <ChevronUp className="w-4 h-4" style={{ color: "var(--brand-on-surface-variant)" }} />
        ) : (
          <ChevronDown className="w-4 h-4" style={{ color: "var(--brand-on-surface-variant)" }} />
        )}
      </button>

      {open && (
        <div className="px-5 pb-5 space-y-4 border-t" style={{ borderColor: "rgba(196,198,207,0.2)" }}>
          <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium mb-1" style={{ color: "var(--brand-on-surface-variant)" }}>
                Label
              </label>
              <input
                className="w-full px-3 py-2 rounded-lg text-sm border"
                style={{ borderColor: "rgba(196,198,207,0.4)" }}
                value={label}
                onChange={(e) => setLabel(e.target.value)}
              />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1" style={{ color: "var(--brand-on-surface-variant)" }}>
                Service fee (minor units)
              </label>
              <input
                className="w-full px-3 py-2 rounded-lg text-sm border"
                style={{ borderColor: "rgba(196,198,207,0.4)" }}
                type="number"
                value={serviceFee}
                onChange={(e) => setServiceFee(e.target.value)}
              />
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium" style={{ color: "var(--brand-navy)" }}>
                Line Items
              </span>
              <button
                type="button"
                className="flex items-center gap-1 text-xs px-2 py-1 rounded-md"
                style={{ color: "var(--brand-viridian)", background: "rgba(63,102,83,0.08)" }}
                onClick={addLineItem}
              >
                <Plus className="w-3 h-3" />
                Add
              </button>
            </div>
            <div className="space-y-2">
              {lineItems.map((li, i) => (
                <div key={i} className="flex gap-2 items-start">
                  <input
                    className="flex-1 px-3 py-2 rounded-lg text-sm border"
                    style={{ borderColor: "rgba(196,198,207,0.4)" }}
                    placeholder="Label"
                    value={li.label}
                    onChange={(e) =>
                      setLineItems((prev) =>
                        prev.map((x, idx) => (idx === i ? { ...x, label: e.target.value } : x)),
                      )
                    }
                  />
                  <input
                    className="w-32 px-3 py-2 rounded-lg text-sm border"
                    style={{ borderColor: "rgba(196,198,207,0.4)" }}
                    placeholder="Amount (minor)"
                    type="number"
                    value={li.amountMinor}
                    onChange={(e) =>
                      setLineItems((prev) =>
                        prev.map((x, idx) =>
                          idx === i ? { ...x, amountMinor: e.target.value } : x,
                        ),
                      )
                    }
                  />
                  <button
                    type="button"
                    className="p-2 rounded-lg"
                    style={{ color: "var(--destructive)" }}
                    onClick={() => removeLineItem(i)}
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div className="flex justify-end">
            <button
              type="button"
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white"
              style={{ background: "var(--brand-viridian)" }}
              onClick={save}
              disabled={upsert.isPending}
            >
              <Save className="w-4 h-4" />
              {upsert.isPending ? "Saving…" : "Save Tier"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function PricingManager() {
  const { data, isLoading } = usePricingTiers();
  const tiers = data?.data ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold" style={{ color: "var(--brand-navy)" }}>
          Pricing Management
        </h1>
        <p className="text-sm mt-1" style={{ color: "var(--brand-on-surface-variant)" }}>
          Configure tier pricing and line items. Changes take effect on the next verification quote.
        </p>
      </div>

      {isLoading ? (
        <div className="text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>
          Loading…
        </div>
      ) : tiers.length === 0 ? (
        <div className="text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>
          No pricing tiers configured yet.
        </div>
      ) : (
        <div className="space-y-3">
          {tiers.map((t) => (
            <TierEditor key={t.id} config={t} />
          ))}
        </div>
      )}
    </div>
  );
}
