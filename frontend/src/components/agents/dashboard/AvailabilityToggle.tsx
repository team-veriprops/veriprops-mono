"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";
import {
  useAgentApplication,
  useUpdateAvailabilityMutation,
} from "@components/agents/libs/useAgentApplicationQueries";
import type { AvailabilityStatus } from "@components/agents/libs/agent-service";

const STATUSES: {
  value: AvailabilityStatus;
  label: string;
  color: string;
  bg: string;
  dot: string;
}[] = [
  { value: "AVAILABLE", label: "Available", color: "#3f6653", bg: "rgba(63,102,83,0.1)", dot: "#3f6653" },
  { value: "LIMITED", label: "Limited", color: "#d97706", bg: "rgba(245,158,11,0.1)", dot: "#d97706" },
  { value: "UNAVAILABLE", label: "Unavailable", color: "#ef4444", bg: "rgba(239,68,68,0.1)", dot: "#ef4444" },
];

export default function AvailabilityToggle() {
  const { data: app } = useAgentApplication();
  const update = useUpdateAvailabilityMutation();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const current =
    STATUSES.find((s) => s.value === app?.availabilityStatus) ?? STATUSES[0];

  useEffect(() => {
    function onOutsideClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onOutsideClick);
    return () => document.removeEventListener("mousedown", onOutsideClick);
  }, []);

  function handleSelect(status: AvailabilityStatus) {
    setOpen(false);
    if (status !== app?.availabilityStatus) update.mutate({ status });
  }

  return (
    <div ref={ref} className="relative shrink-0">
      <button
        onClick={() => setOpen((o) => !o)}
        disabled={update.isPending}
        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold transition-opacity disabled:opacity-60"
        style={{ backgroundColor: current.bg, color: current.color }}
      >
        <span className="w-2 h-2 rounded-full" style={{ backgroundColor: current.dot }} />
        {current.label}
        <ChevronDown className="w-3 h-3 opacity-60" />
      </button>

      {open && (
        <div
          className="absolute right-0 top-full mt-1.5 z-20 rounded-xl py-1 min-w-[160px] shadow-lg"
          style={{
            backgroundColor: "#fff",
            border: "1px solid rgba(196,198,207,0.25)",
          }}
        >
          {STATUSES.map((s) => (
            <button
              key={s.value}
              onClick={() => handleSelect(s.value)}
              className="w-full flex items-center gap-2 px-3 py-2.5 text-xs hover:bg-gray-50 transition-colors"
              style={{ color: s.color }}
            >
              <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: s.dot }} />
              {s.label}
              {s.value === app?.availabilityStatus && (
                <span className="ml-auto text-[10px] opacity-50">current</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
