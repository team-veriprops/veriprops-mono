"use client";

import { useState } from "react";
import { Save } from "lucide-react";
import {
  useUpgradeDeltas,
  useUpsertUpgradeDeltaMutation,
} from "@components/admin/libs/useAdminQueries";
import type { PricingUpgradeDeltaDto } from "@components/admin/libs/admin-service";

function formatMinor(minor: number) {
  return `₦${(minor / 100).toLocaleString("en-NG", { minimumFractionDigits: 0 })}`;
}

interface DeltaRowProps {
  delta: PricingUpgradeDeltaDto;
}

function DeltaRow({ delta }: DeltaRowProps) {
  const [value, setValue] = useState(String(delta.deltaMinor));
  const upsert = useUpsertUpgradeDeltaMutation();

  async function save() {
    await upsert.mutateAsync({
      fromTier: delta.fromTier,
      toTier: delta.toTier,
      deltaMinor: parseInt(value, 10) || 0,
      currency: delta.currency,
    });
  }

  return (
    <div className="flex items-center gap-4 py-3 px-4 rounded-xl" style={{ background: "rgba(63,102,83,0.04)" }}>
      <span className="font-medium text-sm w-40" style={{ color: "var(--brand-navy)" }}>
        {delta.fromTier} → {delta.toTier}
      </span>
      <span className="text-sm w-20" style={{ color: "var(--brand-on-surface-variant)" }}>
        {delta.currency}
      </span>
      <input
        className="w-36 px-3 py-1.5 rounded-lg text-sm border"
        style={{ borderColor: "rgba(196,198,207,0.4)" }}
        type="number"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Delta (minor)"
      />
      <span className="text-xs" style={{ color: "var(--brand-on-surface-variant)" }}>
        = {formatMinor(parseInt(value, 10) || 0)}
      </span>
      <button
        type="button"
        className="ml-auto flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-white"
        style={{ background: "var(--brand-viridian)" }}
        onClick={save}
        disabled={upsert.isPending}
      >
        <Save className="w-3 h-3" />
        {upsert.isPending ? "Saving…" : "Save"}
      </button>
    </div>
  );
}

export default function UpgradeDeltaEditor() {
  const { data, isLoading } = useUpgradeDeltas();
  const deltas = data?.data ?? [];

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold" style={{ color: "var(--brand-navy)" }}>
          Upgrade Deltas
        </h2>
        <p className="text-sm mt-0.5" style={{ color: "var(--brand-on-surface-variant)" }}>
          Amount charged when a customer upgrades between tiers.
        </p>
      </div>

      {isLoading ? (
        <div className="text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>
          Loading…
        </div>
      ) : deltas.length === 0 ? (
        <div className="text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>
          No upgrade deltas configured.
        </div>
      ) : (
        <div className="space-y-2">
          {deltas.map((d) => (
            <DeltaRow key={d.id} delta={d} />
          ))}
        </div>
      )}
    </div>
  );
}
