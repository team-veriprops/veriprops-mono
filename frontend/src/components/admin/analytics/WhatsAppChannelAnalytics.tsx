"use client";

import {
  AlertTriangle,
  BellRing,
  CreditCard,
  MessageSquare,
  Mic,
  RefreshCw,
  Signal,
  UserCheck,
} from "lucide-react";
import { Card } from "@3rdparty/ui/card";
import { AsyncStateComponent } from "@components/ui/AsyncStateComponent";
import { MiniBarBreakdown } from "@components/ui/MiniBarBreakdown";
import { StatCard, StatCardTone } from "@components/ui/StatCard";
import { ChannelCount, WhatsAppChannelAnalytics as ChannelAnalytics } from "@/types/analytics";
import {
  useSyncWhatsAppQualityMutation,
  useWhatsAppChannelAnalyticsQuery,
} from "./libs/useAnalyticsQueries";

/**
 * The WhatsApp channel analytics tab (PRD §7.10, WA-43).
 *
 * All seven metrics the PRD asks to have "instrumented from day one", led by seam
 * conversion — §7.10 calls it "the cost of the A1 trust boundary, measured" and "the
 * single most important number in this channel".
 *
 * Two rendering rules earn their place:
 *
 * - **Every rate shows the counts behind it.** A 60% conversion over three conversations
 *   and the same figure over three hundred call for opposite decisions, and a percentage
 *   alone cannot tell them apart.
 * - **The quality rating shows its sync age.** A GREEN nobody has been able to refresh for
 *   a week is not the same fact as a GREEN from this morning (D81).
 *
 * Charts stay dependency-free CSS bars, matching the standing decision on the platform tab.
 */
export default function WhatsAppChannelAnalytics() {
  const channel = useWhatsAppChannelAnalyticsQuery();
  const sync = useSyncWhatsAppQualityMutation();

  return (
    <div className="space-y-6" data-testid="admin-analytics-whatsapp">
      <AsyncStateComponent<ChannelAnalytics>
        data={channel.data}
        isLoading={channel.isLoading}
        isError={channel.isError}
      >
        {(data) => (
          <>
            <p className="text-sm text-muted-foreground">
              Trailing {data.windowDays} days. Every figure is backend-derived.
            </p>

            <section className="space-y-3">
              <h2 className="text-sm font-semibold text-foreground">
                Intake → payment (seam conversion)
              </h2>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                <StatCard
                  label="Seam conversion"
                  value={asPercent(data.seamConversionRate)}
                  icon={CreditCard}
                  tone={conversionTone(data.seamConversionRate, data.intakeCompleted)}
                  hint={`${data.paymentCompleted} paid of ${data.intakeCompleted} completed intakes`}
                />
                <StatCard
                  label="Intakes completed"
                  value={data.intakeCompleted}
                  icon={MessageSquare}
                  hint="Chat answered everything it can ask"
                />
                <StatCard
                  label="Payments"
                  value={data.paymentCompleted}
                  icon={CreditCard}
                  hint="Cases this channel produced, paid"
                />
              </div>
            </section>

            <section className="space-y-3">
              <h2 className="text-sm font-semibold text-foreground">Demand and bot flow</h2>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <StatCard label="Enquiries" value={data.enquiries} icon={MessageSquare} />
                <StatCard
                  label="Intakes started"
                  value={data.intakeStarted}
                  icon={MessageSquare}
                  hint={`${asPercent(data.enquiryToIntakeRate)} of enquiries`}
                />
                <StatCard
                  label="Escalations"
                  value={data.escalations}
                  icon={AlertTriangle}
                  tone={data.escalationRate > 0.5 ? "warning" : "default"}
                  hint={`${asPercent(data.escalationRate)} of enquiries`}
                />
                <StatCard
                  label="Voice notes"
                  value={data.voiceNotes}
                  icon={Mic}
                  hint="v1.1 transcription trigger data"
                />
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <Card className="space-y-3 p-5">
                  <h3 className="text-sm font-semibold text-foreground">
                    Enquiries by page
                  </h3>
                  <MiniBarBreakdown
                    counts={asCounts(data.enquiriesByPageCode)}
                    emptyText="No attributed enquiries in this window."
                  />
                </Card>

                <Card className="space-y-3 p-5">
                  <h3 className="text-sm font-semibold text-foreground">
                    Why conversations reached a person
                  </h3>
                  <MiniBarBreakdown
                    counts={asCounts(data.escalationsByReason)}
                    emptyText="No escalations in this window."
                  />
                </Card>
              </div>
            </section>

            <section className="space-y-3">
              <h2 className="text-sm font-semibold text-foreground">
                Consent and platform health
              </h2>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <StatCard
                  label="Linked numbers"
                  value={data.linkedNumbers}
                  icon={UserCheck}
                  hint="Customers this channel can reach"
                />
                <StatCard
                  label="Progress updates"
                  value={asPercent(data.utilityOptInRate)}
                  icon={BellRing}
                  hint={`${data.utilityOptIns} of ${data.linkedNumbers} opted in`}
                />
                <StatCard
                  label="News and offers"
                  value={asPercent(data.marketingOptInRate)}
                  icon={BellRing}
                  hint={`${data.marketingOptIns} of ${data.linkedNumbers} opted in`}
                />
                <StatCard
                  label="Meta quality"
                  value={data.numberHealth?.qualityRating ?? "Never synced"}
                  icon={Signal}
                  tone={qualityTone(data.numberHealth?.qualityRating)}
                  hint={qualityHint(data.numberHealth)}
                />
              </div>

              <button
                type="button"
                onClick={() => sync.mutate()}
                disabled={sync.isPending}
                data-testid="whatsapp-quality-sync"
                className="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-black/10 px-3 py-1.5 text-sm text-brand-navy hover:bg-black/3 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <RefreshCw
                  className={sync.isPending ? "h-3.5 w-3.5 animate-spin" : "h-3.5 w-3.5"}
                  aria-hidden="true"
                />
                {sync.isPending ? "Asking Meta…" : "Re-check quality rating"}
              </button>
            </section>
          </>
        )}
      </AsyncStateComponent>
    </div>
  );
}

function asPercent(rate: number): string {
  return `${Math.round(rate * 1000) / 10}%`;
}

function asCounts(rows: ChannelCount[]): Record<string, number> {
  return Object.fromEntries(rows.map((row) => [row.label, row.count]));
}

/**
 * Seam conversion is only worth colouring once there is enough of it to mean something —
 * one unpaid intake is 0%, and painting that red on the channel's first day would train
 * everyone to ignore the tile.
 */
function conversionTone(rate: number, denominator: number): StatCardTone {
  if (denominator < 5) return "default";
  if (rate >= 0.5) return "success";
  return rate >= 0.25 ? "warning" : "danger";
}

function qualityTone(rating?: string): StatCardTone {
  if (rating === "GREEN") return "success";
  if (rating === "YELLOW") return "warning";
  if (rating === "RED") return "danger";
  // UNKNOWN, or never synced. Deliberately not "success" — the absence of Meta's verdict
  // must never read as a clean bill of health (§7.11 treats this as a launch gate).
  return "warning";
}

function qualityHint(health?: { syncedAt?: string; syncError?: string }): string {
  if (!health) return "Not yet read from Meta";
  if (health.syncError) return "Last sync failed — rating may be stale";
  if (!health.syncedAt) return "Not yet read from Meta";
  return `Synced ${new Date(health.syncedAt).toLocaleDateString()}`;
}
