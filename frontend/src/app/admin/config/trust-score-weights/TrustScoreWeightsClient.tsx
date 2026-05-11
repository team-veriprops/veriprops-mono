"use client";

import { useState } from "react";
import { Loader2, Save, AlertTriangle } from "lucide-react";
import {
  useTrustScoreWeights,
  useSetTierWeightsMutation,
} from "@components/admin/libs/useAdminQueries";
import type { TrustScoreWeightConfig } from "@components/admin/libs/admin-service";

const TIERS = ["BASIC", "STANDARD", "PREMIUM"] as const;
const TIER_ROLES: Record<string, string[]> = {
  BASIC: ["REGISTRY"],
  STANDARD: ["FIELD", "SURVEYOR", "REGISTRY"],
  PREMIUM: ["FIELD", "SURVEYOR", "REGISTRY", "LAWYER"],
};

function groupByTier(weights: TrustScoreWeightConfig[]): Record<string, Record<string, number>> {
  const out: Record<string, Record<string, number>> = {};
  for (const w of weights) {
    if (!out[w.tier]) out[w.tier] = {};
    out[w.tier][w.role] = Number(w.weight);
  }
  return out;
}

function TierWeightEditor({ tier, initial }: { tier: string; initial: Record<string, number> }) {
  const roles = TIER_ROLES[tier] ?? [];
  const [values, setValues] = useState<Record<string, number>>(() => {
    const defaults: Record<string, number> = {};
    for (const role of roles) defaults[role] = initial[role] ?? 0;
    return defaults;
  });
  const [error, setError] = useState("");
  const setWeights = useSetTierWeightsMutation();

  const sum = Object.values(values).reduce((a, b) => a + b, 0);

  function handleChange(role: string, val: string) {
    setError("");
    setValues((v) => ({ ...v, [role]: parseFloat(val) || 0 }));
  }

  function handleSave() {
    setError("");
    if (Math.abs(sum - 100) > 0.01) {
      setError(`Weights must sum to 100 (current: ${sum.toFixed(2)})`);
      return;
    }
    setWeights.mutate(
      { tier, weights: values },
      { onError: () => setError("Failed to save weights.") },
    );
  }

  return (
    <div className="rounded-lg border border-gray-200 p-5">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-gray-800">{tier}</h2>
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${Math.abs(sum - 100) < 0.01 ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
          Sum: {sum.toFixed(2)}%
        </span>
      </div>
      <div className="space-y-2">
        {roles.map((role) => (
          <div key={role} className="flex items-center gap-3">
            <label className="w-24 text-sm text-gray-600">{role}</label>
            <input
              type="number"
              min={0}
              max={100}
              step={0.001}
              value={values[role] ?? 0}
              onChange={(e) => handleChange(role, e.target.value)}
              className="w-28 rounded border border-gray-300 px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            <span className="text-sm text-gray-400">%</span>
          </div>
        ))}
      </div>
      {error && (
        <p className="mt-2 flex items-center gap-1 text-xs text-red-600">
          <AlertTriangle className="h-3 w-3" /> {error}
        </p>
      )}
      <button
        onClick={handleSave}
        disabled={setWeights.isPending}
        style={{ cursor: setWeights.isPending ? "not-allowed" : "pointer" }}
        className="mt-3 flex items-center gap-2 rounded bg-indigo-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-60"
      >
        {setWeights.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : <Save className="h-3 w-3" />}
        Save {tier}
      </button>
    </div>
  );
}

export default function TrustScoreWeightsClient() {
  const { data, isLoading } = useTrustScoreWeights();
  const weights = (data as any)?.data ?? [];
  const grouped = groupByTier(weights);

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 py-10 text-gray-500">
        <Loader2 className="h-5 w-5 animate-spin" />
        Loading weights…
      </div>
    );
  }

  return (
    <div className="space-y-4 max-w-xl">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Trust Score Weights</h1>
        <p className="mt-1 text-sm text-gray-500">
          Configure per-tier, per-role weights. Each tier must sum to 100%.
        </p>
      </div>
      {TIERS.map((tier) => (
        <TierWeightEditor key={tier} tier={tier} initial={grouped[tier] ?? {}} />
      ))}
    </div>
  );
}
