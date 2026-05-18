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
    if (!stats?.referralLink) return;
    navigator.clipboard.writeText(stats.referralLink).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  const creditNgn = stats ? stats.creditBalanceNgn.toFixed(0) : "0";
  const hasCreditBalance = stats ? stats.creditBalanceNgn > 0 : false;

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
              title={stats?.referralLink}
            >
              {stats?.referralLink ?? "—"}
            </div>
            <button
              type="button"
              onClick={handleCopy}
              disabled={!stats?.referralLink}
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

      {/* Credit balance banner — only when > 0 */}
      {!isLoading && hasCreditBalance && (
        <div
          className="flex items-center gap-3 p-4 rounded-xl"
          style={{ backgroundColor: "rgba(63,102,83,0.07)", border: "1px solid rgba(63,102,83,0.2)" }}
        >
          <Wallet className="w-4 h-4 flex-shrink-0" style={{ color: "var(--brand-viridian)" }} />
          <p className="text-sm font-semibold" style={{ color: "var(--brand-navy)" }}>
            You have ₦{Number(creditNgn).toLocaleString("en-NG")} in referral credit
          </p>
        </div>
      )}

      {/* Stats grid — always shown once data loads */}
      {!isLoading && stats && (
        <div className="grid grid-cols-2 gap-3">
          <StatCard
            icon={Users}
            label="Total Referred"
            value={String(stats.totalInvited)}
            iconColor="var(--brand-viridian)"
          />
          <StatCard
            icon={Check}
            label="Credited"
            value={`${stats.totalCredited} referral${stats.totalCredited !== 1 ? "s" : ""}`}
            iconColor="var(--brand-viridian)"
          />
          <StatCard
            icon={Clock}
            label="Pending"
            value={`${stats.pendingCount} referral${stats.pendingCount !== 1 ? "s" : ""}`}
            iconColor="#d97706"
          />
          <StatCard
            icon={Gift}
            label="Earn per Referral"
            value="₦1,000"
            iconColor="var(--brand-viridian)"
          />
        </div>
      )}
    </div>
  );
}
