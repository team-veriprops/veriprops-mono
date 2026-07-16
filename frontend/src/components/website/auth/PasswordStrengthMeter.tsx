"use client";

import { useMemo } from "react";
import { scorePassword } from "@components/website/auth/libs/auth/password-strength";
import { cn } from "@lib/utils";

interface PasswordStrengthMeterProps {
  password: string;
  className?: string;
}

const TONES = [
  "bg-danger",         // 0 too weak
  "bg-danger",         // 1 weak
  "bg-warning",        // 2 fair
  "bg-brand-viridian", // 3 strong
  "bg-brand-viridian", // 4 very strong
];

export default function PasswordStrengthMeter({ password, className }: PasswordStrengthMeterProps) {
  const result = useMemo(() => scorePassword(password), [password]);
  const filled = result.score; // 0..4

  return (
    <div className={className}>
      <div className="flex items-center gap-1.5" aria-hidden>
        {[0, 1, 2, 3].map((i) => (
          <span
            key={i}
            className={cn(
              "h-1 flex-1 rounded-full transition-colors",
              i < Math.max(1, filled) ? TONES[filled] : "bg-brand-surface-high"
            )}
          />
        ))}
      </div>
      <div className="mt-1.5 flex items-center justify-between">
        <span
          className={cn(
            "text-xs font-semibold",
            filled >= 3 ? "text-brand-viridian" : filled >= 2 ? "text-warning" : "text-danger"
          )}
        >
          {result.label}
        </span>
        {result.hints[0] && (
          <span className="text-xs text-brand-on-surface-variant">
            {result.hints[0]}
          </span>
        )}
      </div>
    </div>
  );
}
