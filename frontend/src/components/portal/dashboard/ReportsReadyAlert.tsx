"use client";

import Link from "next/link";
import { FileCheck } from "lucide-react";
import { ROUTES } from "@lib/routes";

interface Props {
  count: number;
}

export default function ReportsReadyAlert({ count }: Props) {
  if (count === 0) return null;

  return (
    <div
      className="flex items-center gap-3 p-4 rounded-xl mb-6"
      style={{ backgroundColor: "rgba(245,158,11,0.07)", border: "1px solid rgba(245,158,11,0.2)" }}
    >
      <FileCheck className="w-4 h-4 flex-shrink-0" style={{ color: "#d97706" }} />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold" style={{ color: "var(--brand-navy)" }}>
          {count === 1 ? "1 report is ready" : `${count} reports are ready`}
        </p>
        <p className="text-xs mt-0.5" style={{ color: "var(--brand-on-surface-variant)" }}>
          View your completed verifications to download your reports.
        </p>
      </div>
      <Link
        href={ROUTES.PORTAL.VERIFICATIONS}
        className="flex-shrink-0 px-3 py-1.5 rounded-lg text-xs font-bold transition-opacity hover:opacity-80"
        style={{ backgroundColor: "rgba(245,158,11,0.15)", color: "#d97706" }}
      >
        View →
      </Link>
    </div>
  );
}
