"use client";

import { Check } from "lucide-react";

interface StepperProps {
  steps: string[];
  current: number;            // 0-based
  className?: string;
}

export default function Stepper({ steps, current, className }: StepperProps) {
  return (
    <ol className={className} aria-label="Signup progress" data-testid="signup-stepper">
      <div className="flex items-center gap-2">
        {steps.map((label, i) => {
          const state: "complete" | "current" | "upcoming" =
            i < current ? "complete" : i === current ? "current" : "upcoming";
          return (
            <li key={label} className="flex items-center gap-2 flex-1">
              <span
                className="flex items-center justify-center w-7 h-7 rounded-full text-xs font-semibold transition-colors shrink-0"
                style={{
                  backgroundColor:
                    state === "complete"
                      ? "var(--brand-viridian)"
                      : state === "current"
                      ? "var(--brand-navy)"
                      : "var(--brand-surface-high)",
                  color:
                    state === "upcoming"
                      ? "var(--brand-on-surface-variant)"
                      : "white",
                  boxShadow:
                    state === "current" ? "0 0 0 4px rgba(0,13,34,0.06)" : undefined,
                }}
                aria-current={state === "current" ? "step" : undefined}
              >
                {state === "complete" ? <Check className="w-3.5 h-3.5" strokeWidth={3} /> : i + 1}
              </span>
              <span
                className="hidden sm:inline text-xs font-medium truncate"
                style={{
                  color:
                    state === "current"
                      ? "var(--brand-navy)"
                      : "var(--brand-on-surface-variant)",
                }}
              >
                {label}
              </span>
              {i < steps.length - 1 && (
                <span
                  className="flex-1 h-0.5 rounded-full"
                  style={{
                    backgroundColor:
                      i < current ? "var(--brand-viridian)" : "var(--brand-surface-high)",
                  }}
                  aria-hidden
                />
              )}
            </li>
          );
        })}
      </div>
    </ol>
  );
}
