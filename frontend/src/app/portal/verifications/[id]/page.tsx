"use client";

import { use, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useVerificationTracking, trackingKeys } from "@components/portal/verifications/libs/useTrackingQueries";
import { useVerificationStream } from "@lib/useVerificationStream";
import ProgressTracker from "@components/portal/verifications/ProgressTracker";
import SlaTracker from "@components/portal/verifications/SlaTracker";
import AssignedAgentsCard from "@components/portal/verifications/AssignedAgentsCard";
import StateDetailBanner from "@components/portal/verifications/StateDetailBanner";
import TrustScoreBadge from "@components/shared/TrustScoreBadge";
import Link from "next/link";
import { ROUTES } from "@lib/routes";

export default function VerificationDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const qc = useQueryClient();
  const { data: res, isLoading, error } = useVerificationTracking(id);
  const tracking = (res as any)?.data ?? null;

  const handleStreamEvent = useCallback(() => {
    qc.invalidateQueries({ queryKey: trackingKeys.tracking(id) });
  }, [qc, id]);

  useVerificationStream({ vid: id, onEvent: handleStreamEvent });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-indigo-600" />
      </div>
    );
  }

  if (error || !tracking) {
    return (
      <div className="py-12 text-center text-sm text-red-600">
        Unable to load verification tracking.
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-10 space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold text-gray-900 font-mono">{tracking.vid}</h1>
          {tracking.trustScore !== null && tracking.trustScore !== undefined && (
            <TrustScoreBadge score={Number(tracking.trustScore)} size="sm" />
          )}
        </div>
        <p className="text-sm text-gray-500 mt-1">
          {tracking.tier} Verification
          {tracking.propertyAddress && ` — ${tracking.propertyAddress}`}
        </p>
      </div>

      {/* State banner */}
      <StateDetailBanner status={tracking.status} verificationId={id} />

      {/* Progress */}
      <div className="rounded-lg border border-gray-200 p-5">
        <ProgressTracker status={tracking.status} progressPct={tracking.progressPct} />
      </div>

      {/* SLA */}
      {tracking.sla && (
        <div className="rounded-lg border border-gray-200 p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">Timeline</h2>
          <SlaTracker sla={{
            startedAt: tracking.sla.startedAt,
            targetDays: tracking.sla.targetDays,
            elapsedDays: tracking.sla.elapsedDays,
            onTrack: tracking.sla.onTrack,
          }} />
        </div>
      )}

      {/* Agents */}
      {tracking.assignedAgents?.length > 0 && (
        <div className="rounded-lg border border-gray-200 p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">Assigned Agents</h2>
          <AssignedAgentsCard agents={tracking.assignedAgents.map((a: any) => ({
            role: a.role,
            firstName: a.firstName,
            isTrusted: a.isTrusted,
          }))} />
        </div>
      )}

      {/* Evidence link */}
      {["IN_PROGRESS", "UNDER_REVIEW", "COMPLETED"].includes(tracking.status) && (
        <Link
          href={ROUTES.PORTAL.VERIFICATION_EVIDENCE(id)}
          className="block rounded-lg border border-gray-200 px-5 py-3 text-sm font-medium text-indigo-600 hover:bg-indigo-50 text-center"
        >
          View Evidence
        </Link>
      )}
    </div>
  );
}
