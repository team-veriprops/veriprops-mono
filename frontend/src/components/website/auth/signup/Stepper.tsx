"use client";

import { Check } from "lucide-react";
import { cn } from "@lib/utils";

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
                className={cn(
                  "flex items-center justify-center w-7 h-7 rounded-full text-xs font-semibold transition-colors shrink-0",
                  state === "complete"
                    ? "bg-brand-viridian text-white"
                    : state === "current"
                    ? "bg-brand-navy text-white shadow-[0_0_0_4px_rgba(0,13,34,0.06)]"
                    : "bg-brand-surface-high text-brand-on-surface-variant"
                )}
                aria-current={state === "current" ? "step" : undefined}
              >
                {state === "complete" ? <Check className="w-3.5 h-3.5" strokeWidth={3} /> : i + 1}
              </span>
              <span
                className={cn(
                  "hidden sm:inline text-xs font-medium truncate",
                  state === "current" ? "text-brand-navy" : "text-brand-on-surface-variant"
                )}
              >
                {label}
              </span>
              {i < steps.length - 1 && (
                <span
                  className={cn(
                    "flex-1 h-0.5 rounded-full",
                    i < current ? "bg-brand-viridian" : "bg-brand-surface-high"
                  )}
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
