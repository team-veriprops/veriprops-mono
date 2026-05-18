"use client";

import { useState } from "react";
import { Banknote } from "lucide-react";
import PayoutHistory from "@components/agents/payouts/PayoutHistory";
import WithdrawalModal from "@components/agents/payouts/WithdrawalModal";

export default function AgentPayoutsPage() {
  const [withdrawOpen, setWithdrawOpen] = useState(false);

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--brand-navy)" }}>Payouts</h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--brand-on-surface-variant)" }}>
            Your withdrawal requests and payment history.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setWithdrawOpen(true)}
          style={{ cursor: "pointer", backgroundColor: "var(--brand-viridian)" }}
          className="inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold text-white hover:opacity-90 transition-opacity"
          data-testid="request-withdrawal-button"
        >
          <Banknote className="h-4 w-4" />
          Request Withdrawal
        </button>
      </div>

      <WithdrawalModal open={withdrawOpen} onClose={() => setWithdrawOpen(false)} />

      <div
        className="rounded-xl p-5"
        style={{ backgroundColor: "#fff", border: "1px solid rgba(196,198,207,0.2)" }}
      >
        <h2 className="text-sm font-semibold mb-4" style={{ color: "var(--brand-navy)" }}>Withdrawal History</h2>
        <PayoutHistory />
      </div>
    </div>
  );
}
