"use client";

import { Check } from "lucide-react";

const STEPS = [
  { key: "PAID", label: "Paid" },
  { key: "IN_PROGRESS", label: "Agents Working" },
  { key: "UNDER_REVIEW", label: "Under Review" },
  { key: "COMPLETED", label: "Completed" },
];

const STATUS_STEP_INDEX: Record<string, number> = {
  DRAFT: -1,
  SUBMITTED: -1,
  PAYMENT_PENDING: -1,
  PAID: 0,
  IN_PROGRESS: 1,
  UNDER_REVIEW: 2,
  COMPLETED: 3,
};

interface Props {
  status: string;
  progressPct: number;
}

export default function ProgressTracker({ status, progressPct }: Props) {
  const currentIndex = STATUS_STEP_INDEX[status] ?? -1;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between text-xs text-gray-500">
        <span>Progress</span>
        <span className="font-semibold text-gray-700">{progressPct}%</span>
      </div>
      <div className="w-full h-2 rounded-full bg-gray-100 overflow-hidden">
        <div
          className="h-full rounded-full bg-indigo-500 transition-all duration-500"
          style={{ width: `${progressPct}%` }}
        />
      </div>
      <ol className="flex items-center gap-0">
        {STEPS.map((step, idx) => {
          const done = idx < currentIndex;
          const active = idx === currentIndex;
          return (
            <li key={step.key} className="flex-1 flex flex-col items-center">
              <div
                className={`h-7 w-7 rounded-full flex items-center justify-center text-xs font-bold border-2 transition-colors ${
                  done
                    ? "bg-indigo-600 border-indigo-600 text-white"
                    : active
                    ? "bg-white border-indigo-600 text-indigo-600"
                    : "bg-white border-gray-200 text-gray-300"
                }`}
              >
                {done ? <Check className="h-3.5 w-3.5" /> : idx + 1}
              </div>
              <span
                className={`mt-1.5 text-[10px] text-center ${
                  active ? "text-indigo-700 font-semibold" : done ? "text-gray-600" : "text-gray-300"
                }`}
              >
                {step.label}
              </span>
              {idx < STEPS.length - 1 && (
                <div
                  className={`absolute hidden`}
                />
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
