import type { Metadata } from "next";
import PayoutPanel from "@components/admin/payouts/PayoutPanel";

export const metadata: Metadata = {
  title: "Payouts | Veriprops Admin",
};

export default function FinancePayoutsPage() {
  return (
    <div className="p-6 lg:p-8 max-w-6xl mx-auto">
      <h1 className="text-2xl font-bold mb-6" style={{ color: "var(--brand-navy)" }}>
        Payout Management
      </h1>
      <PayoutPanel />
    </div>
  );
}
