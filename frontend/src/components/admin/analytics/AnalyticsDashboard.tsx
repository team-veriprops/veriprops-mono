"use client";

import { useAnalyticsDashboard } from "@components/admin/libs/useAdminQueries";
import RegionalPerformanceTable from "./RegionalPerformanceTable";

function FunnelStep({ label, count, pct }: { label: string; count: number; pct?: number }) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 rounded-xl p-4" style={{ backgroundColor: "var(--brand-surface-low)" }}>
        <div className="text-xl font-extrabold font-display" style={{ color: "var(--brand-navy)" }}>
          {count.toLocaleString()}
        </div>
        <div className="text-xs mt-0.5" style={{ color: "var(--brand-on-surface-variant)" }}>{label}</div>
      </div>
      {pct !== undefined && (
        <div className="text-xs font-semibold px-2" style={{ color: "var(--brand-viridian)" }}>
          {pct}%
        </div>
      )}
    </div>
  );
}

export default function AnalyticsDashboard() {
  const { data, isLoading } = useAnalyticsDashboard();
  const d = data?.data;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-extrabold font-display" style={{ color: "var(--brand-navy)" }}>
          Analytics
        </h1>
        <p className="text-sm mt-1" style={{ color: "var(--brand-on-surface-variant)" }}>
          Business intelligence and performance metrics
        </p>
      </div>

      {/* Conversion Funnel */}
      <section>
        <h2 className="text-base font-semibold mb-3" style={{ color: "var(--brand-navy)" }}>
          Conversion Funnel
        </h2>
        {isLoading ? (
          <p className="text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>Loading…</p>
        ) : d ? (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <FunnelStep label="Signups" count={d.conversionFunnel.signups} />
            <FunnelStep
              label="Submitted"
              count={d.conversionFunnel.submitted}
            />
            <FunnelStep
              label="Paid"
              count={d.conversionFunnel.paid}
              pct={d.conversionFunnel.signupToPaidPct}
            />
            <FunnelStep
              label="Completed"
              count={d.conversionFunnel.completed}
              pct={d.conversionFunnel.paidToCompletedPct}
            />
          </div>
        ) : null}
      </section>

      {/* Avg Verification Time by Tier */}
      <section>
        <h2 className="text-base font-semibold mb-3" style={{ color: "var(--brand-navy)" }}>
          Avg. Verification Time by Tier
        </h2>
        {isLoading ? (
          <p className="text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>Loading…</p>
        ) : !d?.avgTimeByTier?.length ? (
          <p className="text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>No data yet.</p>
        ) : (
          <div className="flex gap-4 flex-wrap">
            {d.avgTimeByTier.map((t) => (
              <div
                key={t.tier}
                className="rounded-xl px-5 py-4 min-w-[120px]"
                style={{ backgroundColor: "var(--brand-surface-low)" }}
              >
                <div className="text-xl font-extrabold font-display" style={{ color: "var(--brand-navy)" }}>
                  {t.avgHours}h
                </div>
                <div className="text-xs mt-0.5" style={{ color: "var(--brand-on-surface-variant)" }}>
                  {t.tier}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Agent Performance Trends */}
      <section>
        <h2 className="text-base font-semibold mb-3" style={{ color: "var(--brand-navy)" }}>
          Agent Performance Trends (last 6 months)
        </h2>
        {isLoading ? (
          <p className="text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>Loading…</p>
        ) : !d?.agentPerformanceTrends?.length ? (
          <p className="text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>No data yet.</p>
        ) : (
          <div className="overflow-x-auto rounded-2xl" style={{ backgroundColor: "var(--brand-surface-card)", boxShadow: "0 2px 8px rgba(0,13,34,0.04)" }}>
            <table className="w-full text-sm">
              <thead>
                <tr style={{ backgroundColor: "var(--brand-surface-low)" }}>
                  {["Month", "Avg Quality Score", "Reviews"].map((h) => (
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
                {d.agentPerformanceTrends.map((t) => (
                  <tr key={t.period} className="border-t" style={{ borderColor: "var(--brand-surface-low)" }}>
                    <td className="px-4 py-3" style={{ color: "var(--brand-navy)" }}>{t.period}</td>
                    <td className="px-4 py-3">{t.avgQualityScore} / 5</td>
                    <td className="px-4 py-3">{t.totalScores}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Revenue by Location */}
      <section>
        <h2 className="text-base font-semibold mb-3" style={{ color: "var(--brand-navy)" }}>
          Revenue by Location &amp; Tier
        </h2>
        {isLoading ? (
          <p className="text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>Loading…</p>
        ) : !d?.revenueByLocation?.length ? (
          <p className="text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>No data yet.</p>
        ) : (
          <div className="overflow-x-auto rounded-2xl" style={{ backgroundColor: "var(--brand-surface-card)", boxShadow: "0 2px 8px rgba(0,13,34,0.04)" }}>
            <table className="w-full text-sm">
              <thead>
                <tr style={{ backgroundColor: "var(--brand-surface-low)" }}>
                  {["State", "Tier", "Revenue (₦)", "Count"].map((h) => (
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
                {d.revenueByLocation.map((r, i) => (
                  <tr key={i} className="border-t" style={{ borderColor: "var(--brand-surface-low)" }}>
                    <td className="px-4 py-3" style={{ color: "var(--brand-navy)" }}>{r.state}</td>
                    <td className="px-4 py-3">{r.tier}</td>
                    <td className="px-4 py-3">₦{r.revenueNgn.toLocaleString()}</td>
                    <td className="px-4 py-3">{r.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Dispute Rate */}
      {d && (
        <section>
          <h2 className="text-base font-semibold mb-3" style={{ color: "var(--brand-navy)" }}>
            Dispute Rate
          </h2>
          <div className="flex gap-4 flex-wrap">
            {[
              { label: "Completed", value: d.disputeRate.totalCompleted },
              { label: "Disputed", value: d.disputeRate.totalDisputed },
              { label: "Dispute Rate", value: `${d.disputeRate.disputeRatePct}%` },
            ].map((s) => (
              <div
                key={s.label}
                className="rounded-xl px-5 py-4 min-w-[120px]"
                style={{ backgroundColor: "var(--brand-surface-low)" }}
              >
                <div className="text-xl font-extrabold font-display" style={{ color: "var(--brand-navy)" }}>
                  {s.value}
                </div>
                <div className="text-xs mt-0.5" style={{ color: "var(--brand-on-surface-variant)" }}>
                  {s.label}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Regional Performance */}
      <RegionalPerformanceTable />
    </div>
  );
}
