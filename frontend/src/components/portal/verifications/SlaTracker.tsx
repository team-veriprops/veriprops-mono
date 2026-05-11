"use client";

import { Clock } from "lucide-react";

interface SlaData {
  startedAt: string | null;
  targetDays: number;
  elapsedDays: number;
  onTrack: boolean;
}

interface Props {
  sla: SlaData;
}

export default function SlaTracker({ sla }: Props) {
  const pct = Math.min(100, Math.round((sla.elapsedDays / sla.targetDays) * 100));

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-xs">
        <span className="flex items-center gap-1 text-gray-500">
          <Clock className="h-3.5 w-3.5" />
          Estimated Timeline
        </span>
        <span className={`font-semibold ${sla.onTrack ? "text-green-600" : "text-red-600"}`}>
          {sla.onTrack ? "On Track" : "Delayed"}
        </span>
      </div>
      <div className="w-full h-1.5 rounded-full bg-gray-100 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${sla.onTrack ? "bg-green-500" : "bg-red-400"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="text-xs text-gray-400">
        Day {sla.elapsedDays} of {sla.targetDays} target days
      </p>
    </div>
  );
}
