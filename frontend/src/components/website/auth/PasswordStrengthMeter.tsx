"use client";

import { useMemo } from "react";
import { scorePassword } from "@components/website/auth/libs/auth/password-strength";

interface PasswordStrengthMeterProps {
  password: string;
  className?: string;
}

const TONES = [
  "var(--danger)",         // 0 too weak
  "var(--danger)",         // 1 weak
  "var(--warning)",        // 2 fair
  "var(--brand-viridian)", // 3 strong
  "var(--brand-viridian)", // 4 very strong
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
            className="h-1 flex-1 rounded-full transition-colors"
            style={{
              backgroundColor:
                i < Math.max(1, filled) ? TONES[filled] : "var(--brand-surface-high)",
            }}
          />
        ))}
      </div>
      <div className="mt-1.5 flex items-center justify-between">
        <span
          className="text-xs font-semibold"
          style={{
            color:
              filled >= 3
                ? "var(--brand-viridian)"
                : filled >= 2
                ? "var(--warning)"
                : "var(--danger)",
          }}
        >
          {result.label}
        </span>
        {result.hints[0] && (
          <span className="text-xs" style={{ color: "var(--brand-on-surface-variant)" }}>
            {result.hints[0]}
          </span>
        )}
      </div>
    </div>
  );
}
