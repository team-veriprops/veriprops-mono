import EarningsDashboard from "@components/agents/earnings/EarningsDashboard";
import JobBreakdownTable from "@components/agents/earnings/JobBreakdownTable";

export const metadata = { title: "Earnings — Veriprops Agent" };

export default function AgentEarningsPage() {
  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-8">
      <div>
        <h1 className="text-xl font-semibold text-gray-900 mb-1">Earnings</h1>
        <p className="text-sm text-gray-500">Your commission earnings from completed verification tasks.</p>
      </div>
      <EarningsDashboard />
      <div>
        <h2 className="text-base font-semibold text-gray-800 mb-4">Job Breakdown</h2>
        <JobBreakdownTable />
      </div>
    </div>
  );
}
