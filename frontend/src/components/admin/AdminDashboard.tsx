"use client";

import Link from "next/link";
import { Users, ClipboardList, ArrowRight } from "lucide-react";
import { useAgentApplications, useAdminInvitations } from "@components/admin/libs/useAdminQueries";
import { ROUTES } from "@lib/routes";

interface StatCardProps {
  label: string;
  value: number | undefined;
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

export default function AdminDashboard() {
  const { data: applications, isLoading: appsLoading } = useAgentApplications("PENDING");
  const { data: invitations, isLoading: invLoading } = useAdminInvitations("PENDING");

  const pendingApps = applications?.meta?.total ?? applications?.items?.length ?? 0;
  const pendingInvites = invitations?.meta?.total ?? invitations?.items?.length ?? 0;

  return (
    <div className="p-6 lg:p-8 max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-extrabold font-display" style={{ color: "var(--brand-navy)" }}>
          Admin Dashboard
        </h1>
        <p className="text-sm mt-1" style={{ color: "var(--brand-on-surface-variant)" }}>
          Overview of items requiring attention.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <StatCard
          label="Pending Agent Applications"
          value={pendingApps}
          loading={appsLoading}
          href={ROUTES.ADMIN.AGENT_APPLICATIONS}
          accent="rgba(63,102,83,0.1)"
          icon={<ClipboardList className="w-5 h-5" style={{ color: "var(--brand-viridian)" }} strokeWidth={1.75} />}
        />
        <StatCard
          label="Pending Team Invitations"
          value={pendingInvites}
          loading={invLoading}
          href={ROUTES.ADMIN.TEAM}
          accent="rgba(59,130,246,0.1)"
          icon={<Users className="w-5 h-5" style={{ color: "#3b82f6" }} strokeWidth={1.75} />}
        />
      </div>
    </div>
  );
}
