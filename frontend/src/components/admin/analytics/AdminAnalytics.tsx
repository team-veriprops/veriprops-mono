"use client";

import { useState } from "react";
import { BarChart3, MessageSquare } from "lucide-react";
import { Card } from "@3rdparty/ui/card";
import { AsyncStateComponent } from "@components/ui/AsyncStateComponent";
import {
  useAgentTrendsQuery,
  useFunnelQuery,
  useRegionalQuery,
  useRevenueQuery,
  useTimeByTierQuery,
} from "./libs/useAnalyticsQueries";
import { Funnel, Revenue } from "@/types/analytics";
import { cn, formatMinor, humanizeEnumLabel } from "@lib/utils";
import WhatsAppChannelAnalytics from "./WhatsAppChannelAnalytics";

type AnalyticsTab = "platform" | "whatsapp";

const TABS: { id: AnalyticsTab; label: string; icon: typeof BarChart3 }[] = [
  { id: "platform", label: "Platform", icon: BarChart3 },
  { id: "whatsapp", label: "WhatsApp channel", icon: MessageSquare },
];

/**
 * Analytics dashboard (§18.1, D38) — one route, two tabs.
 *
 * **Platform** is the original surface: conversion funnel, avg time by tier, revenue by
 * tier & location, per-state regional performance, and the 6-month agent trend.
 * **WhatsApp channel** is §26.10's seven channel metrics (WA-43). One page rather than two
 * routes, for the reason `AdminMessagesTabs` gives: these are the same question asked of
 * two surfaces, and splitting them makes the channel look like a separate product.
 *
 * Every figure is backend-derived; this only renders. Charts are lightweight, accessible,
 * theme-aware CSS bars (no external charting dependency) — that holds for both tabs.
 */
export default function AdminAnalytics() {
  const [tab, setTab] = useState<AnalyticsTab>("platform");

  return (
    <div className="mx-auto w-full max-w-5xl space-y-6 p-4 sm:p-6" data-testid="admin-analytics">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Analytics</h1>
        <p className="text-sm text-muted-foreground">
          Conversion, turnaround, revenue, agent performance, and the WhatsApp channel — all
          backend-derived.
        </p>
      </div>

      <div
        className="flex w-fit overflow-hidden rounded-lg border border-black/10 text-sm"
        role="tablist"
        aria-label="Analytics sections"
      >
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={tab === id}
            data-testid={`admin-analytics-tab-${id}`}
            onClick={() => setTab(id)}
            className={cn(
              "inline-flex items-center gap-1.5 px-3 py-1.5 cursor-pointer",
              tab === id ? "bg-brand-viridian text-white" : "text-brand-navy hover:bg-black/3",
            )}
          >
            <Icon className="h-3.5 w-3.5" aria-hidden="true" />
            {label}
          </button>
        ))}
      </div>

      {tab === "platform" ? <PlatformAnalytics /> : <WhatsAppChannelAnalytics />}
    </div>
  );
}

function PlatformAnalytics() {
  const funnel = useFunnelQuery();
  const timeByTier = useTimeByTierQuery();
  const revenue = useRevenueQuery();
  const regional = useRegionalQuery();
  const trends = useAgentTrendsQuery();

  return (
    <div className="space-y-6" data-testid="admin-analytics-platform">
      <Card className="space-y-3 p-5">
        <h2 className="text-sm font-semibold text-foreground">Conversion funnel</h2>
        <AsyncStateComponent<Funnel> isLoading={funnel.isLoading} isError={funnel.isError} data={funnel.data}>
          {(f) => <FunnelView funnel={f} />}
        </AsyncStateComponent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="space-y-3 p-5">
          <h2 className="text-sm font-semibold text-foreground">Avg time by tier (days)</h2>
          <AsyncStateComponent data={timeByTier.data} isLoading={timeByTier.isLoading} isError={timeByTier.isError}>
            {(rows) => (
              <BarChart
                data={rows.map((r) => ({ label: humanizeEnumLabel(r.tier), value: r.avgDays, hint: `${r.completedCount} completed` }))}
                format={(v) => `${v.toFixed(1)}d`}
              />
            )}
          </AsyncStateComponent>
        </Card>

        <Card className="space-y-3 p-5">
          <h2 className="text-sm font-semibold text-foreground">Revenue by tier</h2>
          <AsyncStateComponent<Revenue> data={revenue.data} isLoading={revenue.isLoading} isError={revenue.isError}>
            {(rev) => (
              <>
                <p className="text-lg font-bold text-emerald-600 dark:text-emerald-400">
                  {formatMinor(rev.totalMinor)} total
                </p>
                <BarChart
                  data={rev.byTier.map((t) => ({ label: humanizeEnumLabel(t.tier), value: t.revenueMinor, hint: `${t.count} sold` }))}
                  format={(v) => formatMinor(v) ?? "—"}
                />
              </>
            )}
          </AsyncStateComponent>
        </Card>
      </div>

      <Card className="space-y-3 p-5">
        <h2 className="text-sm font-semibold text-foreground">Regional performance</h2>
        <AsyncStateComponent data={regional.data} isLoading={regional.isLoading} isError={regional.isError}>
          {(rows) =>
            rows.length === 0 ? (
              <p className="text-sm text-muted-foreground">No regional data yet.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                      <th className="py-2">State</th>
                      <th className="py-2 text-right">Active</th>
                      <th className="py-2 text-right">Completed</th>
                      <th className="py-2 text-right">Avg trust</th>
                      <th className="py-2 text-right">Revenue</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r) => (
                      <tr key={r.state} className="border-t border-border">
                        <td className="py-2 font-medium">{r.state}</td>
                        <td className="py-2 text-right tabular-nums">{r.active}</td>
                        <td className="py-2 text-right tabular-nums">{r.completed}</td>
                        <td className="py-2 text-right tabular-nums">{r.avgTrustScore ?? "—"}</td>
                        <td className="py-2 text-right tabular-nums">{formatMinor(r.revenueMinor)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          }
        </AsyncStateComponent>
      </Card>

      <Card className="space-y-3 p-5">
        <h2 className="text-sm font-semibold text-foreground">Agent performance (6-month trend)</h2>
        <AsyncStateComponent data={trends.data} isLoading={trends.isLoading} isError={trends.isError}>
          {(t) =>
            t.points.length === 0 ? (
              <p className="text-sm text-muted-foreground">No completed tasks in the trend window yet.</p>
            ) : (
              <BarChart
                data={t.points.map((p) => ({
                  label: p.month, value: p.completedTasks,
                  hint: p.avgQuality != null ? `avg quality ${p.avgQuality}` : undefined,
                }))}
                format={(v) => String(v)}
              />
            )
          }
        </AsyncStateComponent>
      </Card>
    </div>
  );
}

function FunnelView({ funnel }: { funnel: Funnel }) {
  const stages = [
    { label: "Created", value: funnel.created },
    { label: "Submitted", value: funnel.submitted },
    { label: "Paid", value: funnel.paid },
    { label: "Completed", value: funnel.completed },
  ];
  const max = Math.max(1, funnel.created);
  return (
    <div className="space-y-2">
      {stages.map((s) => (
        <div key={s.label} className="flex items-center gap-3">
          <span className="w-24 shrink-0 text-xs text-muted-foreground">{s.label}</span>
          <div className="h-5 flex-1 overflow-hidden rounded bg-muted">
            <div
              className="h-full rounded bg-primary/70"
              style={{ width: `${Math.max(2, (s.value / max) * 100)}%` }}
            />
          </div>
          <span className="w-12 shrink-0 text-right text-sm font-medium tabular-nums">{s.value}</span>
        </div>
      ))}
      <p className="pt-1 text-xs text-muted-foreground">
        Submit {(funnel.submitRate * 100).toFixed(0)}% · Payment {(funnel.paymentRate * 100).toFixed(0)}% ·
        Completion {(funnel.completionRate * 100).toFixed(0)}%
      </p>
    </div>
  );
}

interface Bar {
  label: string;
  value: number;
  hint?: string;
}

function BarChart({ data, format }: { data: Bar[]; format: (v: number) => string }) {
  const max = Math.max(1, ...data.map((d) => d.value));
  if (data.length === 0) return <p className="text-sm text-muted-foreground">No data yet.</p>;
  return (
    <div className="space-y-2">
      {data.map((d) => (
        <div key={d.label} className="flex items-center gap-3">
          <span className="w-24 shrink-0 truncate text-xs text-muted-foreground" title={d.label}>{d.label}</span>
          <div className="h-5 flex-1 overflow-hidden rounded bg-muted">
            <div className="h-full rounded bg-emerald-500/60" style={{ width: `${Math.max(2, (d.value / max) * 100)}%` }} />
          </div>
          <span className="w-28 shrink-0 text-right text-sm font-medium tabular-nums">
            {format(d.value)}
            {d.hint ? <span className="ml-1 text-[10px] font-normal text-muted-foreground">{d.hint}</span> : null}
          </span>
        </div>
      ))}
    </div>
  );
}
