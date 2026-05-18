"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Verification } from "@components/portal/verifications/libs/verification-service";
import { STATUS_LABELS, STATUS_COLORS } from "@components/portal/verifications/libs/status";
import { ROUTES } from "@lib/routes";

const SLA_DAYS: Record<string, number> = {
  BASIC: 5,
  STANDARD: 7,
  PREMIUM: 10,
};

function estimatedCompletion(v: Verification): string | null {
  if (!v.paidAt) return null;
  const days = SLA_DAYS[v.tier] ?? 7;
  const d = new Date(v.paidAt);
  d.setDate(d.getDate() + days);
  return d.toLocaleDateString("en-NG", { day: "numeric", month: "short", year: "numeric" });
}

interface Props {
  verification: Verification;
}

export default function ActiveVerificationCard({ verification: v }: Props) {
  const { bg, text } = STATUS_COLORS[v.status] ?? STATUS_COLORS.DRAFT;
  const location = [v.property?.state, v.property?.lga].filter(Boolean).join(", ");
  const address = v.property?.addressLine ?? location ?? "—";
  const eta = estimatedCompletion(v);

  return (
    <Link
      href={ROUTES.PORTAL.VERIFICATION_DETAIL(v.id)}
      className="block rounded-xl p-4 transition-all duration-150 hover:shadow-md group"
      style={{ backgroundColor: "#fff", border: "1px solid rgba(196,198,207,0.15)", boxShadow: "0 1px 4px rgba(0,13,34,0.04)" }}
    >
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-sm font-mono font-bold flex-shrink-0" style={{ color: "var(--brand-navy)" }}>
            {v.vid}
          </span>
          <span
            className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold flex-shrink-0"
            style={{ backgroundColor: bg, color: text }}
          >
            {STATUS_LABELS[v.status]}
          </span>
        </div>
        <ArrowRight
          className="w-4 h-4 flex-shrink-0 mt-0.5 transition-transform group-hover:translate-x-0.5"
          style={{ color: "var(--brand-on-surface-variant)" }}
        />
      </div>

      <p className="text-xs truncate mb-1" style={{ color: "var(--brand-navy)", fontWeight: 500 }}>
        {address}
      </p>

      <div className="flex items-center gap-3 text-xs" style={{ color: "var(--brand-on-surface-variant)" }}>
        <span>{v.tier} tier</span>
        {eta && <span>· Est. {eta}</span>}
      </div>
    </Link>
  );
}
