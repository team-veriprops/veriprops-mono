"use client";

import { useRegionalPerformance } from "@components/admin/libs/useAdminQueries";

export default function RegionalPerformanceTable() {
  const { data, isLoading } = useRegionalPerformance();
  const regions = data?.data?.regions ?? [];

  return (
    <div
      className="rounded-2xl overflow-hidden"
      style={{ backgroundColor: "var(--brand-surface-card)", boxShadow: "0px 4px 16px rgba(0,13,34,0.06)" }}
    >
      <div className="px-6 py-4 border-b" style={{ borderColor: "var(--brand-surface-low)" }}>
        <h3 className="font-semibold" style={{ color: "var(--brand-navy)" }}>Regional Performance</h3>
        <p className="text-xs mt-0.5" style={{ color: "var(--brand-on-surface-variant)" }}>
          Active and completed verifications by state
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr style={{ backgroundColor: "var(--brand-surface-low)" }}>
              {["State", "Active", "Completed", "Avg Trust Score", "Revenue (₦)"].map((h) => (
                <th
                  key={h}
                  className="text-xs font-semibold uppercase tracking-wider px-4 py-3 text-left"
                  style={{ color: "var(--brand-on-surface-variant)" }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={5} className="text-center py-8" style={{ color: "var(--brand-on-surface-variant)" }}>
                  Loading…
                </td>
              </tr>
            ) : regions.length === 0 ? (
              <tr>
                <td colSpan={5} className="text-center py-8" style={{ color: "var(--brand-on-surface-variant)" }}>
                  No regional data yet.
                </td>
              </tr>
            ) : (
              regions.map((r) => (
                <tr key={r.region} className="border-t" style={{ borderColor: "var(--brand-surface-low)" }}>
                  <td className="px-4 py-3 font-medium" style={{ color: "var(--brand-navy)" }}>{r.region}</td>
                  <td className="px-4 py-3">{r.activeCount}</td>
                  <td className="px-4 py-3">{r.completedCount}</td>
                  <td className="px-4 py-3">
                    {r.avgTrustScore != null ? r.avgTrustScore.toFixed(1) : "—"}
                  </td>
                  <td className="px-4 py-3">₦{r.revenueNgn.toLocaleString()}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
