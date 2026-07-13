"use client";

import { ShieldCheck, Lock, Eye } from "lucide-react";
import BrandLogo from "@/components/ui/BrandLogo";

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
    <div className="min-h-screen grid lg:grid-cols-[5fr_7fr] bg-brand-surface">
      {/* ─── Left: brand panel ───────────────────────────────────── */}
      <aside
        className="hidden lg:flex flex-col justify-between p-12 xl:p-16 relative overflow-hidden text-white bg-[linear-gradient(135deg,var(--brand-navy)_0%,var(--brand-navy-deep)_60%,#0f2d50_100%)]"
      >
        {/* Ambient grid + glow */}
        <div
          className="absolute inset-0 pointer-events-none opacity-40 bg-[radial-gradient(circle_at_1px_1px,rgba(255,255,255,0.05)_1px,transparent_0)] bg-size-[32px_32px]"
        />
        <div
          className="absolute -top-40 -right-40 w-[520px] h-[520px] rounded-full pointer-events-none bg-[radial-gradient(circle,rgba(63,102,83,0.28)_0%,transparent_70%)]"
        />

        <BrandLogo variant="light" />

        <div className="relative z-10 max-w-md">
          <span className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs font-semibold uppercase tracking-widest bg-white/8 border border-white/12">
            <span
              className="w-1.5 h-1.5 rounded-full bg-brand-viridian-light"
            />
            Trusted by Nigerians worldwide
          </span>

          <h2 className="mt-6 text-4xl xl:text-5xl font-extrabold font-display editorial-spacing leading-[1.05]">
            {panelHeading}
          </h2>
          <p className="mt-5 text-base text-white/70 leading-relaxed">{panelCopy}</p>

          <ul className="mt-10 space-y-4">
            {PILLARS.map(({ icon: Icon, label }) => (
              <li key={label} className="flex items-center gap-3 text-sm text-white/85">
                <span
                  className="w-9 h-9 flex items-center justify-center rounded-lg shrink-0 bg-brand-viridian/18 border border-brand-viridian-light/20"
                >
                  <Icon className="w-4 h-4 text-brand-viridian-light" />
                </span>
                {label}
              </li>
            ))}
          </ul>
        </div>

        <p className="relative z-10 text-xs text-white/60">
          © 2026 Veriprops. We reduce uncertainty. We do not eliminate it.
        </p>
      </aside>

      {/* ─── Right: form panel ───────────────────────────────────── */}
      <main className="flex flex-col px-6 sm:px-10 lg:px-16 py-10 lg:py-16 min-h-screen">
        {/* Mobile header */}
        <div className="lg:hidden mb-8 flex items-center justify-between">
          <BrandLogo variant="dark" size="sm" />
        </div>

        <div className="flex-1 flex items-center">
          <div className="w-full max-w-[440px] mx-auto">{children}</div>
        </div>
      </main>
    </div>
  );
}
