"use client";

import { useState } from "react";
import ContentItemTable from "./ContentItemTable";

export default function AreaInsightPanel() {
  const [state, setState] = useState("");
  const [lga, setLga] = useState("");
  const [applied, setApplied] = useState<{ state: string; lga: string } | null>(null);

  const apply = () => setApplied({ state: state.trim(), lga: lga.trim() });
  const clear = () => {
    setState("");
    setLga("");
    setApplied(null);
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label className="block text-xs font-medium mb-1" style={{ color: "var(--brand-on-surface-variant)" }}>
            State
          </label>
          <input
            type="text"
            value={state}
            onChange={(e) => setState(e.target.value)}
            placeholder="e.g. Lagos"
            className="rounded-lg px-3 py-2 text-sm border"
            style={{ borderColor: "rgba(196,198,207,0.4)", color: "var(--brand-navy)", background: "var(--brand-surface)", width: "160px" }}
          />
        </div>
        <div>
          <label className="block text-xs font-medium mb-1" style={{ color: "var(--brand-on-surface-variant)" }}>
            LGA
          </label>
          <input
            type="text"
            value={lga}
            onChange={(e) => setLga(e.target.value)}
            placeholder="e.g. Ikeja"
            className="rounded-lg px-3 py-2 text-sm border"
            style={{ borderColor: "rgba(196,198,207,0.4)", color: "var(--brand-navy)", background: "var(--brand-surface)", width: "160px" }}
          />
        </div>
        <button
          type="button"
          onClick={apply}
          className="px-4 py-2 rounded-lg text-sm font-medium text-white"
          style={{ background: "var(--brand-viridian)" }}
        >
          Filter
        </button>
        {applied && (
          <button
            type="button"
            onClick={clear}
            className="px-3 py-2 rounded-lg text-sm border"
            style={{ borderColor: "rgba(196,198,207,0.4)", color: "var(--brand-on-surface-variant)" }}
          >
            Clear
          </button>
        )}
      </div>

      <ContentItemTable itemType="AREA_INSIGHT" />
    </div>
  );
}
