"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ShieldCheck, Monitor, Link2, ChevronLeft, CheckCircle2 } from "lucide-react";
import { ROUTES } from "@lib/routes";
import { cn } from "@lib/utils";

interface AccountShellProps {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}

const NAV = [
  { href: ROUTES.ACCOUNT.SECURITY, label: "Security activity",  icon: ShieldCheck },
  { href: ROUTES.ACCOUNT.DEVICES,  label: "Connected devices",  icon: Monitor },
  { href: ROUTES.ACCOUNT.LINKED,   label: "Linked accounts",    icon: Link2 },
];

export default function AccountShell({ title, subtitle, children }: AccountShellProps) {
  const pathname = usePathname();
  return (
    <div className="min-h-screen bg-[var(--brand-surface-base)]">
      <header
        className="px-6 sm:px-10 lg:px-16 py-5 flex items-center justify-between"
        style={{ borderBottom: "1px solid rgba(196,198,207,0.25)" }}
      >
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
        <Link
          href={ROUTES.PORTAL.DASHBOARD}
          className="inline-flex items-center gap-1.5 text-sm font-semibold"
          style={{ color: "var(--brand-on-surface-variant)" }}
        >
          <ChevronLeft className="w-4 h-4" /> Back to portal
        </Link>
      </header>

      <div className="max-w-6xl mx-auto px-6 sm:px-10 lg:px-16 py-10 lg:py-14 grid lg:grid-cols-[260px_1fr] gap-10">
        <aside>
          <h2
            className="text-xs font-semibold uppercase tracking-widest mb-4"
            style={{ color: "var(--brand-on-surface-variant)" }}
          >
            Account & security
          </h2>
          <nav className="flex flex-col gap-1">
            {NAV.map(({ href, label, icon: Icon }) => {
              const active = pathname === href;
              return (
                <Link
                  key={href}
                  href={href}
                  className={cn(
                    "flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-colors",
                    active
                      ? "bg-[var(--brand-surface-card)] shadow-sm"
                      : "hover:bg-[var(--brand-surface-low)]",
                  )}
                  style={{
                    color: active ? "var(--brand-navy)" : "var(--brand-on-surface-variant)",
                  }}
                >
                  <Icon
                    className="w-4 h-4"
                    style={{ color: active ? "var(--brand-viridian)" : "currentColor" }}
                  />
                  {label}
                </Link>
              );
            })}
          </nav>
        </aside>

        <main>
          <div className="mb-8">
            <h1
              className="text-3xl font-extrabold font-display editorial-spacing"
              style={{ color: "var(--brand-navy)" }}
            >
              {title}
            </h1>
            {subtitle && (
              <p className="mt-2 text-base" style={{ color: "var(--brand-on-surface-variant)" }}>
                {subtitle}
              </p>
            )}
          </div>
          {children}
        </main>
      </div>
    </div>
  );
}
