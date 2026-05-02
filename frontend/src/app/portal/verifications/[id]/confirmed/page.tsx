"use client";

import { use } from "react";
import { Button } from "@3rdparty/ui/button";
import { CheckCircle2, Clock } from "lucide-react";
import Link from "next/link";
import { useVerification } from "@components/portal/verifications/libs/useVerificationQueries";
import { ROUTES } from "@lib/routes";

export default function VerificationConfirmedPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { data, isLoading } = useVerification(id);

  if (isLoading || !data) {
    return (
      <div
        className="text-sm py-12 text-center"
        style={{ color: "var(--brand-on-surface-variant)" }}
      >
        Loading…
      </div>
    );
  }

  const eta = etaForTier(data.tier, data.paidAt ?? data.submittedAt);

  return (
    <div className="max-w-2xl mx-auto px-4 py-12">
      <div
        className="rounded-2xl p-8 text-center space-y-6"
        style={{
          backgroundColor: "var(--brand-surface-card)",
          boxShadow: "0px 24px 48px rgba(0,13,34,0.06)",
        }}
      >
        <div
          className="mx-auto w-16 h-16 rounded-full flex items-center justify-center"
          style={{ backgroundColor: "rgba(58,154,106,0.08)", color: "var(--success)" }}
        >
          <CheckCircle2 className="w-8 h-8" />
        </div>
        <div>
          <h1
            className="text-3xl font-semibold tracking-tight"
            style={{ color: "var(--brand-navy)", fontFamily: "var(--font-display, Manrope)" }}
          >
            Verification confirmed
          </h1>
          <p className="text-sm mt-2 leading-6" style={{ color: "var(--brand-on-surface-variant)" }}>
            Your verification ID is <span className="font-mono font-semibold">{data.vid}</span>.
            We&apos;ll start work as soon as our admins assign your agents.
          </p>
        </div>

        <div
          className="rounded-xl p-4 text-sm flex items-center justify-center gap-2"
          style={{
            backgroundColor: "var(--brand-surface-low)",
            color: "var(--brand-navy)",
          }}
        >
          <Clock className="w-4 h-4" />
          <span>Estimated completion: {eta}</span>
        </div>

        <Button asChild>
          <Link href={ROUTES.PORTAL.VERIFICATION_DETAIL(id)}>Track my verification</Link>
        </Button>
      </div>
    </div>
  );
}

function etaForTier(tier: string, paidAt: string | null): string {
  const days = tier === "BASIC" ? 5 : tier === "STANDARD" ? 7 : 10;
  if (!paidAt) return `~${days} business days`;
  const target = new Date(paidAt);
  let added = 0;
  while (added < days) {
    target.setDate(target.getDate() + 1);
    const dow = target.getDay();
    if (dow !== 0 && dow !== 6) added++;
  }
  return target.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}
