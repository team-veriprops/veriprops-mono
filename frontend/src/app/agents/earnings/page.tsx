import EarningsDashboard from "@components/agents/earnings/EarningsDashboard";
import JobBreakdownTable from "@components/agents/earnings/JobBreakdownTable";

export const metadata = { title: "Earnings — Veriprops Agent" };

export default function AgentEarningsPage() {
  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-8">
      <div>
        <h1 className="text-xl font-semibold mb-1" style={{ color: "var(--brand-navy)" }}>Earnings</h1>
        <p className="text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>
          Your commission earnings from completed verification tasks.
        </p>
      </div>
      <EarningsDashboard />
      <div>
        <h2 className="text-base font-semibold mb-4" style={{ color: "var(--brand-navy)" }}>Job Breakdown</h2>
        <JobBreakdownTable />
      </div>
    </div>
  );
}
