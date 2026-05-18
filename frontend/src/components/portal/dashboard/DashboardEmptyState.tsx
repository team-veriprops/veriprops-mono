"use client";

import Link from "next/link";
import { ShieldCheck, Plus } from "lucide-react";
import { ROUTES } from "@lib/routes";

export default function DashboardEmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center px-6">
      <div
        className="w-16 h-16 rounded-full flex items-center justify-center mb-5"
        style={{ backgroundColor: "rgba(63,102,83,0.08)" }}
      >
        <ShieldCheck className="w-8 h-8" style={{ color: "var(--brand-viridian)" }} />
      </div>
      <h2 className="text-lg font-extrabold font-display mb-2" style={{ color: "var(--brand-navy)" }}>
        Your first verification is one step away
      </h2>
      <p className="text-sm max-w-xs mb-6" style={{ color: "var(--brand-on-surface-variant)" }}>
        Protect your property investment with a professional verification from our trusted agents on the ground.
      </p>
      <Link
        href={ROUTES.PORTAL.VERIFICATIONS_NEW}
        className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-bold transition-all duration-200 hover:opacity-90 hover:scale-[0.98] signature-gradient text-white"
        style={{ boxShadow: "0 4px 14px -3px rgba(0,13,34,0.3)" }}
      >
        <Plus className="w-4 h-4" />
        Verify a Property
      </Link>
    </div>
  );
}
