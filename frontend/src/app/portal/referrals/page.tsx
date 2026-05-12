"use client";

import { useState } from "react";
import { Copy, Check, Gift, Users, Clock, Wallet } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { httpClient } from "@/containers";
import { ReferralService } from "@components/portal/referrals/referral-service";

const referralService = new ReferralService(httpClient);

function StatCard({
  icon: Icon,
  label,
  value,
  iconColor,
}: {
  icon: React.ElementType;
  label: string;
  value: string;
  iconColor: string;
}) {
  return (
    <div
      className="flex items-start gap-3 p-4 rounded-xl"
      style={{ backgroundColor: "#fff", border: "1px solid rgba(196,198,207,0.15)", boxShadow: "0 2px 8px rgba(0,13,34,0.04)" }}
    >
      <div
        className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0"
        style={{ backgroundColor: "rgba(63,102,83,0.08)" }}
      >
        <Icon className="w-4 h-4" style={{ color: iconColor }} />
      </div>
      <div>
        <div className="text-xl font-bold" style={{ color: "var(--brand-navy)" }}>{value}</div>
        <div className="text-xs mt-0.5" style={{ color: "var(--brand-on-surface-variant)" }}>{label}</div>
      </div>
    </div>
  );
}

export default function PortalReferralsPage() {
  const { data: stats, isLoading } = useQuery({
    queryKey: ["referrals", "my-stats"],
    queryFn: async () => (await referralService.getMyStats()).data ?? null,
    staleTime: 60_000,
  });

  const [copied, setCopied] = useState(false);

  function handleCopy() {
    if (!stats?.link) return;
    navigator.clipboard.writeText(stats.link).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  const creditNgn = stats ? (stats.creditBalanceKobo / 100).toFixed(0) : "0";
  const isEmpty = !stats || stats.timesRedeemed === 0;

  return (
    <div className="max-w-2xl mx-auto px-4 py-8 space-y-8">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 mb-1">
          <Gift className="w-5 h-5" style={{ color: "var(--brand-viridian)" }} />
          <h1 className="text-xl font-semibold" style={{ color: "var(--brand-navy)" }}>Referrals</h1>
        </div>
        <p className="text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>
          Invite friends and earn ₦1,000 credit when they complete their first verification.
        </p>
      </div>

      {/* Referral link card */}
      <div
        className="rounded-2xl p-5 space-y-3"
        style={{ backgroundColor: "#fff", border: "1px solid rgba(196,198,207,0.15)", boxShadow: "0 2px 8px rgba(0,13,34,0.04)" }}
      >
        <label className="block text-xs font-semibold" style={{ color: "var(--brand-navy)" }}>
          Your Referral Link
        </label>
        {isLoading ? (
          <div className="h-10 rounded-lg animate-pulse" style={{ backgroundColor: "rgba(0,13,34,0.05)" }} />
        ) : (
          <div className="flex items-center gap-2">
            <div
              className="flex-1 min-w-0 px-3 py-2 rounded-lg text-sm font-mono truncate"
              style={{ backgroundColor: "rgba(0,13,34,0.04)", color: "var(--brand-navy)", border: "1px solid rgba(196,198,207,0.2)" }}
              title={stats?.link}
            >
              {stats?.link ?? "—"}
            </div>
            <button
              type="button"
              onClick={handleCopy}
              disabled={!stats?.link}
              className="flex-shrink-0 flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-bold transition-all hover:opacity-90 disabled:opacity-40 text-white"
              style={{ backgroundColor: copied ? "#3f6653" : "var(--brand-navy)" }}
              data-testid="referral-copy-link"
            >
              {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
              {copied ? "Copied!" : "Copy"}
            </button>
          </div>
        )}
        {stats?.code && (
          <p className="text-xs" style={{ color: "var(--brand-on-surface-variant)" }}>
            Code: <span className="font-mono font-semibold">{stats.code}</span>
          </p>
        )}
      </div>

      {/* Stats grid */}
      {!isLoading && stats && (
        <div className="grid grid-cols-2 gap-3">
          <StatCard
            icon={Users}
            label="Total Invited"
            value={String(stats.timesRedeemed)}
            iconColor="var(--brand-viridian)"
          />
          <StatCard
            icon={Check}
            label="Credited (NGN)"
            value={`₦${Number(stats.creditedNgn).toLocaleString("en-NG")}`}
            iconColor="var(--brand-viridian)"
          />
          <StatCard
            icon={Clock}
            label="Pending Credits (NGN)"
            value={`₦${Number(stats.pendingCreditsNgn).toLocaleString("en-NG")}`}
            iconColor="#d97706"
          />
          <StatCard
            icon={Wallet}
            label="Credit Balance"
            value={`₦${Number(creditNgn).toLocaleString("en-NG")}`}
            iconColor="var(--brand-viridian)"
          />
        </div>
      )}

      {/* Empty state */}
      {!isLoading && isEmpty && (
        <div className="text-center py-8">
          <div
            className="w-14 h-14 rounded-full flex items-center justify-center mx-auto mb-4"
            style={{ backgroundColor: "rgba(63,102,83,0.08)" }}
          >
            <Gift className="w-6 h-6" style={{ color: "var(--brand-viridian)" }} />
          </div>
          <p className="text-sm font-medium mb-1" style={{ color: "var(--brand-navy)" }}>
            No referrals yet
          </p>
          <p className="text-xs" style={{ color: "var(--brand-on-surface-variant)" }}>
            Share your link above to start earning credit when friends verify their properties.
          </p>
        </div>
      )}
    </div>
  );
}
