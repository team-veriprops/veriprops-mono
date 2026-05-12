"use client";

import { Star, TrendingUp, Clock, Briefcase, Calendar, CheckCircle2 } from "lucide-react";
import { useAgentProfile } from "@components/agents/libs/useAgentApplicationQueries";
import { ROUTES } from "@lib/routes";
import Link from "next/link";

function AvailabilityBadge({ status }: { status: string }) {
  const config = {
    AVAILABLE: { label: "Available", color: "#3f6653", bg: "rgba(63,102,83,0.1)", dot: "#3f6653" },
    LIMITED: { label: "Limited", color: "#d97706", bg: "rgba(245,158,11,0.1)", dot: "#d97706" },
    UNAVAILABLE: { label: "Unavailable", color: "#ef4444", bg: "rgba(239,68,68,0.1)", dot: "#ef4444" },
  }[status] ?? { label: status, color: "#6b7280", bg: "rgba(107,114,128,0.1)", dot: "#6b7280" };

  return (
    <span
      className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold"
      style={{ backgroundColor: config.bg, color: config.color }}
    >
      <span className="w-2 h-2 rounded-full" style={{ backgroundColor: config.dot }} />
      {config.label}
    </span>
  );
}

function ScoreBar({ value, max = 100 }: { value: number; max?: number }) {
  const pct = Math.min(100, (value / max) * 100);
  return (
    <div className="h-1.5 rounded-full bg-gray-100 overflow-hidden">
      <div
        className="h-full rounded-full transition-all"
        style={{ width: `${pct}%`, backgroundColor: "var(--brand-viridian)" }}
      />
    </div>
  );
}

function StarRating({ score }: { score: number }) {
  return (
    <div className="flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map((i) => (
        <Star
          key={i}
          className="w-4 h-4"
          fill={score >= i ? "var(--brand-viridian)" : "none"}
          style={{ color: score >= i ? "var(--brand-viridian)" : "#d1d5db" }}
        />
      ))}
      <span className="ml-1 text-sm font-semibold" style={{ color: "var(--brand-navy)" }}>
        {score.toFixed(1)}
      </span>
    </div>
  );
}

export default function AgentProfilePage() {
  const { data: profile, isLoading } = useAgentProfile();

  if (isLoading) {
    return (
      <div className="p-6 text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>
        Loading profile…
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="p-6 text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>
        Profile unavailable.
      </div>
    );
  }

  const { application, metrics, isTopAgent } = profile;
  const activeSince = metrics.activeSince
    ? new Date(metrics.activeSince).toLocaleDateString("en-NG", { month: "long", year: "numeric" })
    : "—";

  return (
    <div className="max-w-2xl mx-auto px-4 py-8 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--brand-navy)" }}>
            My Profile
          </h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--brand-on-surface-variant)" }}>
            Performance metrics and settings
          </p>
        </div>
        <div className="flex items-center gap-2">
          {isTopAgent && (
            <span
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold"
              style={{ backgroundColor: "rgba(245,158,11,0.12)", color: "#b45309" }}
            >
              <Star className="w-3 h-3" fill="#b45309" />
              Top Agent
            </span>
          )}
          <AvailabilityBadge status={application.availabilityStatus} />
          <Link
            href={ROUTES.AGENT.SETTINGS_AVAILABILITY}
            className="text-xs underline"
            style={{ color: "var(--brand-viridian)" }}
          >
            Edit
          </Link>
        </div>
      </div>

      {/* Summary stats */}
      <div
        className="grid grid-cols-2 gap-4 p-4 rounded-2xl"
        style={{ backgroundColor: "#fff", border: "1px solid rgba(196,198,207,0.15)", boxShadow: "0 2px 8px rgba(0,13,34,0.04)" }}
      >
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ backgroundColor: "rgba(63,102,83,0.08)" }}>
            <Briefcase className="w-4 h-4" style={{ color: "var(--brand-viridian)" }} />
          </div>
          <div>
            <div className="text-xl font-bold" style={{ color: "var(--brand-navy)" }}>{metrics.totalJobs}</div>
            <div className="text-xs" style={{ color: "var(--brand-on-surface-variant)" }}>Total Jobs</div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ backgroundColor: "rgba(63,102,83,0.08)" }}>
            <Calendar className="w-4 h-4" style={{ color: "var(--brand-viridian)" }} />
          </div>
          <div>
            <div className="text-sm font-bold" style={{ color: "var(--brand-navy)" }}>{activeSince}</div>
            <div className="text-xs" style={{ color: "var(--brand-on-surface-variant)" }}>Active Since</div>
          </div>
        </div>
      </div>

      {/* Metrics */}
      <div
        className="rounded-2xl overflow-hidden"
        style={{ backgroundColor: "#fff", border: "1px solid rgba(196,198,207,0.15)", boxShadow: "0 2px 8px rgba(0,13,34,0.04)" }}
      >
        <div className="px-5 py-4" style={{ borderBottom: "1px solid rgba(196,198,207,0.12)" }}>
          <h2 className="text-sm font-semibold" style={{ color: "var(--brand-navy)" }}>Performance Metrics</h2>
        </div>
        <div className="divide-y" style={{ borderColor: "rgba(196,198,207,0.12)" }}>
          {/* Completion rate */}
          <div className="px-5 py-4 space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4" style={{ color: "var(--brand-viridian)" }} />
                <span className="text-sm font-medium" style={{ color: "var(--brand-navy)" }}>Completion Rate</span>
              </div>
              <span className="text-sm font-bold" style={{ color: "var(--brand-navy)" }}>
                {metrics.completionRate.toFixed(0)}%
              </span>
            </div>
            <ScoreBar value={metrics.completionRate} />
          </div>

          {/* Accuracy */}
          <div className="px-5 py-4 space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Star className="w-4 h-4" style={{ color: "var(--brand-viridian)" }} />
                <span className="text-sm font-medium" style={{ color: "var(--brand-navy)" }}>Accuracy Score</span>
              </div>
              <StarRating score={metrics.accuracyScore} />
            </div>
            <ScoreBar value={metrics.accuracyScore} max={5} />
          </div>

          {/* Timeliness */}
          <div className="px-5 py-4 space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4" style={{ color: "var(--brand-viridian)" }} />
                <span className="text-sm font-medium" style={{ color: "var(--brand-navy)" }}>Timeliness</span>
              </div>
              <span className="text-sm font-bold" style={{ color: "var(--brand-navy)" }}>
                {metrics.timelinessScore.toFixed(0)}%
              </span>
            </div>
            <ScoreBar value={metrics.timelinessScore} />
          </div>
        </div>
      </div>

      {/* Coverage */}
      <div
        className="rounded-2xl p-5"
        style={{ backgroundColor: "#fff", border: "1px solid rgba(196,198,207,0.15)", boxShadow: "0 2px 8px rgba(0,13,34,0.04)" }}
      >
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold" style={{ color: "var(--brand-navy)" }}>Coverage</h2>
          <Link
            href={ROUTES.AGENT.SETTINGS_COVERAGE}
            className="text-xs underline"
            style={{ color: "var(--brand-viridian)" }}
          >
            Edit
          </Link>
        </div>
        <p className="text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>
          {application.coverageStates.length > 0
            ? application.coverageStates.join(", ")
            : "No coverage areas set"}
        </p>
        {application.maxTravelKm != null && (
          <p className="text-xs mt-1" style={{ color: "var(--brand-on-surface-variant)" }}>
            Max travel: {application.maxTravelKm} km
          </p>
        )}
      </div>
    </div>
  );
}
