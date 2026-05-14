"use client";

import Link from "next/link";
import { Activity, ArrowRight, Clock, DollarSign, UserCheck, AlertTriangle, ClipboardList } from "lucide-react";
import { useMissionControl } from "@components/admin/libs/useAdminQueries";
import { ROUTES } from "@lib/routes";

interface StatCardProps {
  label: string;
  value: string | number | undefined;
  loading: boolean;
  href: string;
  icon: React.ReactNode;
  accent: string;
}

function StatCard({ label, value, loading, href, icon, accent }: StatCardProps) {
  return (
    <Link
      href={href}
      className="group flex items-center gap-5 p-6 rounded-2xl bg-white transition-all duration-200 hover:-translate-y-0.5"
      style={{ border: "1px solid rgba(196,198,207,0.15)", boxShadow: "0 2px 8px rgba(0,13,34,0.04)" }}
    >
      <div
        className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0"
        style={{ backgroundColor: accent }}
      >
        {icon}
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-2xl font-extrabold font-display" style={{ color: "var(--brand-navy)" }}>
          {loading ? "—" : (value ?? 0)}
        </div>
        <div className="text-sm mt-0.5" style={{ color: "var(--brand-on-surface-variant)" }}>
          {label}
        </div>
      </div>
      <ArrowRight
        className="w-4 h-4 flex-shrink-0 transition-transform group-hover:translate-x-0.5"
        style={{ color: "var(--brand-on-surface-variant)" }}
      />
    </Link>
  );
}

export default function MissionControlPanel() {
  const { data, isLoading } = useMissionControl();
  const mc = data?.data;

  const revenueDisplay = mc
    ? `₦${(mc.revenueTotalNgn / 1000).toFixed(0)}k`
    : undefined;

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold" style={{ color: "var(--brand-navy)" }}>
          Mission Control
        </h2>
        <p className="text-sm mt-0.5" style={{ color: "var(--brand-on-surface-variant)" }}>
          Live operational health
        </p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <StatCard
          label="Active Verifications"
          value={mc?.activeVerifications}
          loading={isLoading}
          href={ROUTES.ADMIN.VERIFICATIONS}
          accent="rgba(63,102,83,0.1)"
          icon={<Activity className="w-5 h-5" style={{ color: "var(--brand-viridian)" }} strokeWidth={1.75} />}
        />
        <StatCard
          label="Pending Assignments"
          value={mc?.pendingAssignments}
          loading={isLoading}
          href={ROUTES.ADMIN.VERIFICATIONS}
          accent="rgba(59,130,246,0.1)"
          icon={<ClipboardList className="w-5 h-5" style={{ color: "#3b82f6" }} strokeWidth={1.75} />}
        />
        <StatCard
          label="Stuck Jobs"
          value={mc?.stuckJobs}
          loading={isLoading}
          href={ROUTES.ADMIN.VERIFICATIONS}
          accent="rgba(234,88,12,0.1)"
          icon={<Clock className="w-5 h-5" style={{ color: "#ea580c" }} strokeWidth={1.75} />}
        />
        <StatCard
          label="SLA At Risk"
          value={mc?.slaAtRiskCount}
          loading={isLoading}
          href={ROUTES.ADMIN.VERIFICATIONS}
          accent="rgba(186,26,26,0.08)"
          icon={<AlertTriangle className="w-5 h-5" style={{ color: "var(--destructive)" }} strokeWidth={1.75} />}
        />
        <StatCard
          label="Total Revenue"
          value={revenueDisplay}
          loading={isLoading}
          href={ROUTES.ADMIN.FINANCE_PAYMENTS}
          accent="rgba(63,102,83,0.08)"
          icon={<DollarSign className="w-5 h-5" style={{ color: "var(--brand-viridian)" }} strokeWidth={1.75} />}
        />
        <StatCard
          label="Available Agents"
          value={mc?.availableAgents}
          loading={isLoading}
          href={ROUTES.ADMIN.AGENT_APPLICATIONS}
          accent="rgba(16,185,129,0.1)"
          icon={<UserCheck className="w-5 h-5" style={{ color: "#10b981" }} strokeWidth={1.75} />}
        />
      </div>
    </div>
  );
}
