import type { Metadata } from "next";
import Link from "next/link";
import { ROUTES } from "@lib/routes";

export const metadata: Metadata = {
  title: "Finance | Veriprops Admin",
};

const sections = [
  {
    href: ROUTES.ADMIN.FINANCE_PAYMENTS,
    title: "Payments",
    description: "View all payments, filter by status or method, and confirm wire transfers.",
  },
  {
    href: ROUTES.ADMIN.FINANCE_PAYOUTS,
    title: "Payouts",
    description: "Review agent payout requests and approve disbursements.",
  },
  {
    href: ROUTES.ADMIN.FINANCE_COMMISSIONS,
    title: "Commissions",
    description: "Breakdown of agent commissions by status and period.",
  },
];

export default function FinancePage() {
  return (
    <div className="p-6 lg:p-8 max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold" style={{ color: "var(--brand-navy)" }}>
          Finance
        </h1>
        <p className="text-sm mt-1" style={{ color: "var(--brand-on-surface-variant)" }}>
          Manage payments, payouts, and commission records.
        </p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {sections.map((s) => (
          <Link
            key={s.href}
            href={s.href}
            className="p-5 rounded-xl border transition hover:-translate-y-0.5"
            style={{ borderColor: "rgba(196,198,207,0.25)", background: "#fff" }}
          >
            <div className="font-semibold mb-1" style={{ color: "var(--brand-navy)" }}>
              {s.title}
            </div>
            <div className="text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>
              {s.description}
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
