"use client";

import { Briefcase, Star, Clock, Wallet } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useAgentMetrics } from "@components/agents/libs/useAgentApplicationQueries";
import { earningsService } from "@components/agents/earnings/libs/earnings-service";
import type { AgentMetrics } from "@components/agents/libs/agent-service";
import type { EarningsSummary } from "@components/agents/earnings/libs/earnings-service";

function fmt(n: number) {
  return `₦${n.toLocaleString("en-NG", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

function KpiCard({
  label,
  value,
  sub,
  icon: Icon,
  highlight,
}: {
  label: string;
  value: string;
  sub?: string;
  icon: React.ElementType;
  highlight?: boolean;
}) {
  return (
    <div
      className="rounded-xl border p-4 flex items-start gap-3"
      style={{
        backgroundColor: highlight ? "rgba(63,102,83,0.06)" : "#fff",
        borderColor: highlight ? "rgba(63,102,83,0.3)" : "rgba(196,198,207,0.2)",
        boxShadow: "0 1px 4px rgba(0,13,34,0.04)",
      }}
    >
      <div
        className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0 mt-0.5"
        style={{ backgroundColor: "rgba(63,102,83,0.1)" }}
      >
        <Icon className="w-4 h-4" style={{ color: "var(--brand-viridian)" }} />
      </div>
      <div className="min-w-0">
        <div className="text-xl font-bold leading-tight" style={{ color: "var(--brand-navy)" }}>
          {value}
        </div>
        {sub && (
          <div className="text-xs mt-0.5 font-medium" style={{ color: "var(--brand-viridian)" }}>
            {sub}
          </div>
        )}
        <div className="text-xs mt-0.5" style={{ color: "var(--brand-on-surface-variant)" }}>
          {label}
        </div>
      </div>
    </div>
  );
}

function SkeletonCard() {
  return (
    <div
      className="rounded-xl border h-20 animate-pulse"
      style={{ backgroundColor: "#f3f4f6", borderColor: "rgba(196,198,207,0.2)" }}
    />
  );
}

export default function AgentKpiBar() {
  const { data: metrics, isLoading: metricsLoading } = useAgentMetrics();
  const { data: earningsData, isLoading: earningsLoading } = useQuery({
    queryKey: ["agent", "earnings"],
    queryFn: () => earningsService.getSummary(),
    staleTime: 60_000,
  });

  const m: AgentMetrics | null = metrics ?? null;
  const summary: EarningsSummary | null = (earningsData as any)?.data ?? null;

  if (metricsLoading || earningsLoading) {
    return (
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <SkeletonCard />
        <SkeletonCard />
        <SkeletonCard />
        <SkeletonCard />
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <KpiCard
        label="Total Jobs"
        value={String(m?.totalJobs ?? 0)}
        icon={Briefcase}
      />
      <KpiCard
        label="Accuracy Score"
        value={m ? `${m.accuracyScore.toFixed(1)} / 5` : "—"}
        icon={Star}
      />
      <KpiCard
        label="Timeliness"
        value={m ? `${m.timelinessScore.toFixed(0)}%` : "—"}
        icon={Clock}
      />
      <KpiCard
        label="Available Earnings"
        value={summary ? fmt(summary.totalAvailable) : "—"}
        sub={summary?.totalPending ? `+ ${fmt(summary.totalPending)} pending` : undefined}
        icon={Wallet}
        highlight
      />
    </div>
  );
}
