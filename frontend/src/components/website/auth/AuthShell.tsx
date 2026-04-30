"use client";

import Link from "next/link";
import { CheckCircle2, ShieldCheck, Lock, Eye } from "lucide-react";
import { ROUTES } from "@lib/routes";

interface AuthShellProps {
  children: React.ReactNode;
  /** Heading shown on the left brand panel (desktop only). */
  panelHeading?: string;
  /** Sub-copy shown on the left brand panel. */
  panelCopy?: string;
}

const PILLARS = [
  { icon: ShieldCheck, label: "Process integrity, end-to-end" },
  { icon: Lock,        label: "Bank-grade security & encryption" },
  { icon: Eye,         label: "Independent agents, never the seller" },
];

export default function AuthShell({
  children,
  panelHeading = "We reduce uncertainty.",
  panelCopy = "We do not eliminate it. Every Veriprops verification follows a rigorous, evidence-backed methodology — so you can act on facts, not hearsay.",
}: AuthShellProps) {
  return (
    <div className="min-h-screen grid lg:grid-cols-[5fr_7fr] bg-[var(--brand-surface-base)]">
      {/* ─── Left: brand panel ───────────────────────────────────── */}
      <aside
        className="hidden lg:flex flex-col justify-between p-12 xl:p-16 relative overflow-hidden text-white"
        style={{
          background:
            "linear-gradient(135deg, var(--brand-navy) 0%, var(--brand-navy-deep) 60%, #0f2d50 100%)",
        }}
      >
        {/* Ambient grid + glow */}
        <div
          className="absolute inset-0 pointer-events-none opacity-40"
          style={{
            backgroundImage:
              "radial-gradient(circle at 1px 1px, rgba(255,255,255,0.05) 1px, transparent 0)",
            backgroundSize: "32px 32px",
          }}
        />
        <div
          className="absolute -top-40 -right-40 w-[520px] h-[520px] rounded-full pointer-events-none"
          style={{
            background:
              "radial-gradient(circle, rgba(63,102,83,0.28) 0%, transparent 70%)",
          }}
        />

        <Link href={ROUTES.HOME} className="relative z-10 inline-flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-lg bg-white/10 backdrop-blur-sm flex items-center justify-center border border-white/15">
            <CheckCircle2 className="w-5 h-5 text-white" strokeWidth={2.5} />
          </div>
          <span className="text-xl font-extrabold tracking-tight font-display editorial-spacing">
            Veriprops
          </span>
        </Link>

        <div className="relative z-10 max-w-md">
          <span className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs font-semibold uppercase tracking-widest bg-white/8 border border-white/12">
            <span
              className="w-1.5 h-1.5 rounded-full"
              style={{ backgroundColor: "var(--brand-viridian-light)" }}
            />
            The Sovereign Curator
          </span>

          <h2 className="mt-6 text-4xl xl:text-5xl font-extrabold font-display editorial-spacing leading-[1.05]">
            {panelHeading}
          </h2>
          <p className="mt-5 text-base text-white/70 leading-relaxed">{panelCopy}</p>

          <ul className="mt-10 space-y-4">
            {PILLARS.map(({ icon: Icon, label }) => (
              <li key={label} className="flex items-center gap-3 text-sm text-white/85">
                <span
                  className="w-9 h-9 flex items-center justify-center rounded-lg shrink-0"
                  style={{
                    backgroundColor: "rgba(63,102,83,0.18)",
                    border: "1px solid rgba(190,234,209,0.2)",
                  }}
                >
                  <Icon className="w-4 h-4" style={{ color: "var(--brand-viridian-light)" }} />
                </span>
                {label}
              </li>
            ))}
          </ul>
        </div>

        <p className="relative z-10 text-xs text-white/40">
          © 2026 Veriprops. We reduce uncertainty. We do not eliminate it.
        </p>
      </aside>

      {/* ─── Right: form panel ───────────────────────────────────── */}
      <main className="flex flex-col px-6 sm:px-10 lg:px-16 py-10 lg:py-16 min-h-screen">
        {/* Mobile header */}
        <div className="lg:hidden mb-8 flex items-center justify-between">
          <Link href={ROUTES.HOME} className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg signature-gradient flex items-center justify-center">
              <CheckCircle2 className="w-4.5 h-4.5 text-white" strokeWidth={2.5} />
            </div>
            <span
              className="text-lg font-extrabold tracking-tight font-display editorial-spacing"
              style={{ color: "var(--brand-navy)" }}
            >
              Veriprops
            </span>
          </Link>
        </div>

        <div className="flex-1 flex items-center">
          <div className="w-full max-w-[440px] mx-auto">{children}</div>
        </div>
      </main>
    </div>
  );
}
