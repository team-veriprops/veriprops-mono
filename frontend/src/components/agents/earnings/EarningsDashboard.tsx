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
  return (
    <div
      className={`rounded-lg border p-5 ${
        highlight ? "border-indigo-200 bg-indigo-50" : "border-gray-200 bg-white"
      }`}
      data-testid={`earnings-stat-${label.toLowerCase().replace(/\s+/g, "-")}`}
    >
      <div className="flex items-center gap-2 mb-2">
        <Icon className={`h-4 w-4 ${highlight ? "text-indigo-600" : "text-gray-500"}`} />
        <p className="text-xs font-medium uppercase tracking-wide text-gray-500">{label}</p>
      </div>
      <p className={`text-2xl font-bold ${highlight ? "text-indigo-700" : "text-gray-900"}`}>
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
        <Loader2 className="h-5 w-5 animate-spin text-indigo-500" />
      </div>
    );
  }

  if (error || !summary) {
    return <p className="text-sm text-red-600 py-4">Failed to load earnings data.</p>;
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
