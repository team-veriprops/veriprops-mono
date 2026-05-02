"use client";

import { use } from "react";
import { useRouter } from "next/navigation";
import { useVerification } from "@components/portal/verifications/libs/useVerificationQueries";
import PaymentStep from "@components/portal/verifications/payment/PaymentStep";
import { ROUTES } from "@lib/routes";

export default function PayPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
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
  return (
    <div className="max-w-3xl mx-auto px-4 py-10">
      <PaymentStep
        verification={data}
        onPaid={() => router.push(ROUTES.PORTAL.VERIFICATION_CONFIRMED(id))}
      />
    </div>
  );
}
