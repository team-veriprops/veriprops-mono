"use client";

import { useQuery } from "@tanstack/react-query";
import { Loader2, TrendingUp, Clock, CheckCircle, Wallet } from "lucide-react";
import { earningsService } from "./libs/earnings-service";
import type { EarningsSummary } from "./libs/earnings-service";

function StatCard({
  label,
  value,
  icon: Icon,
  highlight,
}: {
  label: string;
  value: string;
  icon: React.ElementType;
  highlight?: boolean;
}) {
  const cardStyle = highlight
    ? { backgroundColor: "rgba(63,102,83,0.08)", border: "1px solid rgba(63,102,83,0.2)" }
    : { backgroundColor: "#fff", border: "1px solid rgba(196,198,207,0.2)" };

  return (
    <div
      className="rounded-xl p-5"
      style={cardStyle}
      data-testid={`earnings-stat-${label.toLowerCase().replace(/\s+/g, "-")}`}
    >
      <div className="flex items-center gap-2 mb-2">
        <Icon
          className="h-4 w-4"
          style={{ color: highlight ? "var(--brand-viridian)" : "var(--brand-on-surface-variant)" }}
        />
        <p
          className="text-xs font-medium uppercase tracking-wide"
          style={{ color: "var(--brand-on-surface-variant)" }}
        >
          {label}
        </p>
      </div>
      <p
        className="text-2xl font-bold"
        style={{ color: highlight ? "var(--brand-viridian)" : "var(--brand-navy)" }}
      >
        {value}
      </p>
    </div>
  );
}

function fmt(n: number) {
  return `₦${n.toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
}

export default function EarningsDashboard() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["agent", "earnings"],
    queryFn: () => earningsService.getSummary(),
  });
  const summary: EarningsSummary | null = (data as any)?.data ?? null;

  if (isLoading) {
    return (
      <div className="flex justify-center py-10">
        <Loader2 className="h-5 w-5 animate-spin" style={{ color: "var(--brand-viridian)" }} />
      </div>
    );
  }

  if (error || !summary) {
    return (
      <p className="text-sm py-4" style={{ color: "#ef4444" }}>
        Failed to load earnings data.
      </p>
    );
  }

  return (
    <div data-testid="earnings-dashboard" className="space-y-6">
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatCard label="Available" value={fmt(summary.totalAvailable)} icon={Wallet} highlight />
        <StatCard label="Lifetime" value={fmt(summary.totalLifetime)} icon={TrendingUp} />
        <StatCard label="Pending" value={fmt(summary.totalPending)} icon={Clock} />
        <StatCard label="Total Paid" value={fmt(summary.totalPaid)} icon={CheckCircle} />
      </div>
    </div>
  );
}
