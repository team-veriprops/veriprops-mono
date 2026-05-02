"use client";

import { use } from "react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useVerification } from "@components/portal/verifications/libs/useVerificationQueries";
import { ROUTES } from "@lib/routes";

export default function VerificationDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();
  const { data, isLoading } = useVerification(id);

  // Phase 9 ships the live tracking dashboard; for now we route by status.
  useEffect(() => {
    if (!data) return;
    if (data.status === "DRAFT") router.replace(ROUTES.PORTAL.VERIFICATIONS_NEW);
    if (data.status === "PAID" || data.status === "IN_PROGRESS") {
      router.replace(ROUTES.PORTAL.VERIFICATION_CONFIRMED(id));
    }
  }, [data, id, router]);

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
  return (
    <div className="max-w-3xl mx-auto px-4 py-10">
      <h1
        className="text-3xl font-semibold tracking-tight"
        style={{ color: "var(--brand-navy)", fontFamily: "var(--font-display, Manrope)" }}
      >
        {data.vid}
      </h1>
      <p className="text-sm mt-2" style={{ color: "var(--brand-on-surface-variant)" }}>
        Status: {data.status}
      </p>
    </div>
  );
}
