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
          <h1 className="text-xl font-semibold text-gray-900">Payouts</h1>
          <p className="text-sm text-gray-500 mt-0.5">Your withdrawal requests and payment history.</p>
        </div>
        <button
          type="button"
          onClick={() => setWithdrawOpen(true)}
          style={{ cursor: "pointer" }}
          className="inline-flex items-center gap-2 rounded-md bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          data-testid="request-withdrawal-button"
        >
          <Banknote className="h-4 w-4" />
          Request Withdrawal
        </button>
      </div>

      <WithdrawalModal open={withdrawOpen} onClose={() => setWithdrawOpen(false)} />

      <div className="rounded-lg border border-gray-200 bg-white p-5">
        <h2 className="text-sm font-semibold text-gray-800 mb-4">Withdrawal History</h2>
        <PayoutHistory />
      </div>
    </div>
  );
}
