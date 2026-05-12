"use client";

import { useState, useEffect } from "react";
import { Activity, AlertCircle, Save } from "lucide-react";
import { useAgentApplication, useUpdateAvailabilityMutation } from "@components/agents/libs/useAgentApplicationQueries";
import type { AvailabilityStatus } from "@components/agents/libs/agent-service";

const AVAILABILITY_OPTIONS: {
  value: AvailabilityStatus;
  label: string;
  description: string;
  dotColor: string;
}[] = [
  {
    value: "AVAILABLE",
    label: "Available",
    description: "You can receive new job assignments.",
    dotColor: "#3f6653",
  },
  {
    value: "LIMITED",
    label: "Limited",
    description: "You are available but with reduced capacity.",
    dotColor: "#d97706",
  },
  {
    value: "UNAVAILABLE",
    label: "Unavailable",
    description: "You will not receive new job assignments.",
    dotColor: "#ef4444",
  },
];

export default function AgentAvailabilityPage() {
  const { data: app, isLoading } = useAgentApplication();
  const mutation = useUpdateAvailabilityMutation();

  const [selected, setSelected] = useState<AvailabilityStatus>("AVAILABLE");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (app?.availabilityStatus) {
      setSelected(app.availabilityStatus as AvailabilityStatus);
    }
  }, [app]);

  async function handleSave() {
    await mutation.mutateAsync({ status: selected });
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
    <div className="max-w-lg mx-auto px-4 py-8 space-y-6">
      <div>
        <div className="flex items-center gap-2 mb-1">
          <Activity className="w-4 h-4" style={{ color: "var(--brand-viridian)" }} />
          <h1 className="text-xl font-semibold" style={{ color: "var(--brand-navy)" }}>Availability</h1>
        </div>
        <p className="text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>
          Control whether you receive new job assignments.
        </p>
      </div>

      <div
        className="rounded-2xl overflow-hidden"
        style={{ backgroundColor: "#fff", border: "1px solid rgba(196,198,207,0.15)", boxShadow: "0 2px 8px rgba(0,13,34,0.04)" }}
      >
        <div className="divide-y" style={{ borderColor: "rgba(196,198,207,0.12)" }}>
          {AVAILABILITY_OPTIONS.map((opt) => {
            const isSelected = selected === opt.value;
            return (
              <label
                key={opt.value}
                className="flex items-center gap-4 px-5 py-4 cursor-pointer transition-colors hover:bg-gray-50"
              >
                <input
                  type="radio"
                  name="availability"
                  value={opt.value}
                  checked={isSelected}
                  onChange={() => { setSelected(opt.value); setSaved(false); }}
                  className="sr-only"
                  data-testid={`availability-${opt.value.toLowerCase()}`}
                />
                <span className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: opt.dotColor }} />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium" style={{ color: "var(--brand-navy)" }}>{opt.label}</div>
                  <div className="text-xs mt-0.5" style={{ color: "var(--brand-on-surface-variant)" }}>{opt.description}</div>
                </div>
                <div
                  className="w-5 h-5 rounded-full border-2 flex items-center justify-center flex-shrink-0"
                  style={{
                    borderColor: isSelected ? "var(--brand-viridian)" : "rgba(196,198,207,0.6)",
                    backgroundColor: isSelected ? "var(--brand-viridian)" : "transparent",
                  }}
                >
                  {isSelected && <div className="w-2 h-2 rounded-full bg-white" />}
                </div>
              </label>
            );
          })}
        </div>
      </div>

      {/* Auto-set warning */}
      {app?.availabilityStatus === "UNAVAILABLE" && (
        <div
          className="flex items-start gap-2 px-4 py-3 rounded-xl text-xs"
          style={{ backgroundColor: "rgba(239,68,68,0.06)", color: "#ef4444", border: "1px solid rgba(239,68,68,0.15)" }}
        >
          <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <span>
            Your status may have been automatically set to Unavailable due to active task capacity.
            You can manually override it here.
          </span>
        </div>
      )}

      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={handleSave}
          disabled={mutation.isPending}
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-bold transition-all duration-200 hover:opacity-90 disabled:opacity-50 text-white"
          style={{ backgroundColor: "var(--brand-viridian)" }}
          data-testid="availability-save"
        >
          <Save className="w-4 h-4" />
          {mutation.isPending ? "Saving…" : "Save Availability"}
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
