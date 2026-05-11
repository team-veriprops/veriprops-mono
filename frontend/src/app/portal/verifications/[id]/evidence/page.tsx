"use client";

import { use } from "react";
import { ArrowLeft, Loader2 } from "lucide-react";
import Link from "next/link";
import { ROUTES } from "@lib/routes";
import { useVerificationEvidence } from "@components/portal/verifications/libs/useTrackingQueries";
import EvidenceFeed from "@components/portal/verifications/EvidenceFeed";

export default function EvidencePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data: res, isLoading } = useVerificationEvidence(id);
  const items = (res as any)?.data ?? [];

  return (
    <div className="max-w-2xl mx-auto px-4 py-10 space-y-6">
      <div className="flex items-center gap-3">
        <Link
          href={ROUTES.PORTAL.VERIFICATION_TRACKING(id)}
          className="text-gray-500 hover:text-gray-700 flex items-center gap-1 text-sm"
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </Link>
        <h1 className="text-xl font-semibold text-gray-900">Evidence</h1>
      </div>

      {isLoading ? (
        <div className="flex items-center gap-2 py-12 text-gray-500">
          <Loader2 className="h-5 w-5 animate-spin" />
          Loading evidence…
        </div>
      ) : (
        <div className="space-y-6">
          <EvidenceFeed items={items.map((i: any) => ({
            id: i.id,
            evidenceType: i.evidenceType,
            fileUrl: i.fileUrl,
            gpsLat: i.gpsLat,
            gpsLng: i.gpsLng,
            capturedAt: i.capturedAt,
            agentRole: i.agentRole,
          }))} />
        </div>
      )}
    </div>
  );
}
