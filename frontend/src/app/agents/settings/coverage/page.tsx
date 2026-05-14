"use client";

import { useState, useEffect } from "react";
import { MapPin, Save } from "lucide-react";
import { useAgentApplication, useUpdateCoverageMutation } from "@components/agents/libs/useAgentApplicationQueries";
import { nigerianStates } from "@lib/nigerianLocations";


function StateToggle({
  label,
  value,
  selected,
  onToggle,
}: {
  label: string;
  value: string;
  selected: boolean;
  onToggle: (v: string) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onToggle(value)}
      className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all border"
      style={
        selected
          ? { backgroundColor: "rgba(63,102,83,0.12)", color: "var(--brand-viridian)", borderColor: "var(--brand-viridian)" }
          : { backgroundColor: "#fff", color: "var(--brand-on-surface-variant)", borderColor: "rgba(196,198,207,0.4)" }
      }
    >
      {label}
    </button>
  );
}

export default function AgentCoveragePage() {
  const { data: app, isLoading } = useAgentApplication();
  const mutation = useUpdateCoverageMutation();

  const [selectedStates, setSelectedStates] = useState<string[]>([]);
  const [maxTravelKm, setMaxTravelKm] = useState<string>("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (app) {
      setSelectedStates(app.coverageStates ?? []);
      setMaxTravelKm(app.maxTravelKm != null ? String(app.maxTravelKm) : "");
    }
  }, [app]);

  function toggleState(v: string) {
    setSelectedStates((prev) =>
      prev.includes(v) ? prev.filter((s) => s !== v) : [...prev, v],
    );
    setSaved(false);
  }

  async function handleSave() {
    await mutation.mutateAsync({
      coverageStates: selectedStates,
      coverageLgas: app?.coverageLgas ?? [],
      maxTravelKm: maxTravelKm ? Number(maxTravelKm) : undefined,
    });
    setSaved(true);
  }

  if (isLoading) {
    return (
      <div className="p-6 text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>
        Loading…
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-8 space-y-6">
      <div>
        <div className="flex items-center gap-2 mb-1">
          <MapPin className="w-4 h-4" style={{ color: "var(--brand-viridian)" }} />
          <h1 className="text-xl font-semibold" style={{ color: "var(--brand-navy)" }}>Coverage Settings</h1>
        </div>
        <p className="text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>
          Select the states you can cover for verification tasks.
        </p>
      </div>

      <div
        className="rounded-2xl p-5 space-y-5"
        style={{ backgroundColor: "#fff", border: "1px solid rgba(196,198,207,0.15)", boxShadow: "0 2px 8px rgba(0,13,34,0.04)" }}
      >
        <div>
          <label className="block text-xs font-semibold mb-3" style={{ color: "var(--brand-navy)" }}>
            Coverage States ({selectedStates.length} selected)
          </label>
          <div className="flex flex-wrap gap-2">
            {nigerianStates.map((s) => (
              <StateToggle
                key={s.value}
                label={s.label}
                value={s.value.toUpperCase()}
                selected={selectedStates.includes(s.value.toUpperCase())}
                onToggle={toggleState}
              />
            ))}
          </div>
        </div>

        <div>
          <label
            htmlFor="max-travel"
            className="block text-xs font-semibold mb-1.5"
            style={{ color: "var(--brand-navy)" }}
          >
            Max Travel Distance (km)
          </label>
          <input
            id="max-travel"
            type="number"
            min={0}
            max={2000}
            placeholder="e.g. 50"
            value={maxTravelKm}
            onChange={(e) => { setMaxTravelKm(e.target.value); setSaved(false); }}
            className="w-32 px-3 py-2 rounded-lg text-sm border outline-none focus:ring-2"
            style={{
              border: "1px solid rgba(196,198,207,0.4)",
              color: "var(--brand-navy)",
            }}
            data-testid="coverage-max-travel"
          />
        </div>
      </div>

      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={handleSave}
          disabled={mutation.isPending}
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-bold transition-all duration-200 hover:opacity-90 disabled:opacity-50 text-white"
          style={{ backgroundColor: "var(--brand-viridian)" }}
          data-testid="coverage-save"
        >
          <Save className="w-4 h-4" />
          {mutation.isPending ? "Saving…" : "Save Coverage"}
        </button>
        {saved && (
          <span className="text-xs font-medium" style={{ color: "var(--brand-viridian)" }}>
            Saved successfully
          </span>
        )}
        {mutation.isError && (
          <span className="text-xs" style={{ color: "#ef4444" }}>
            Failed to save. Please try again.
          </span>
        )}
      </div>
    </div>
  );
}
