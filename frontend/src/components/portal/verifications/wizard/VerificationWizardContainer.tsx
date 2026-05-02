"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Stepper from "./Stepper";
import PropertyStep, { PropertyStepValues } from "./PropertyStep";
import TierStep from "../pricing/TierStep";
import ConsentStep from "./ConsentStep";
import PaymentStep from "../payment/PaymentStep";
import {
  useActiveDraft,
  useSaveDraftMutation,
  useSelectTierMutation,
  useSubmitVerificationMutation,
} from "../libs/useVerificationQueries";
import type { VerificationTier } from "../libs/verification-service";
import { ROUTES } from "@lib/routes";
import { getErrorMessage } from "@lib/utils";

const STEPS = ["Property", "Tier", "Consent", "Payment"];

const TIER_PARAM_MAP: Record<string, VerificationTier> = {
  basic: "BASIC",
  standard: "STANDARD",
  premium: "PREMIUM",
};

export default function VerificationWizardContainer() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { data: draft, isLoading } = useActiveDraft();
  const [step, setStep] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const verificationId = draft?.id ?? "";
  const saveDraft = useSaveDraftMutation(verificationId);
  const selectTier = useSelectTierMutation(verificationId);
  const submitVerification = useSubmitVerificationMutation(verificationId);

  // Resume — but never go past the Tier step automatically; users always
  // see consents & payment afresh.
  useEffect(() => {
    if (!draft) return;
    if (draft.status !== "DRAFT") {
      // Past draft → redirect to confirmed/payment screen.
      if (draft.status === "PAID" || draft.status === "IN_PROGRESS") {
        router.replace(ROUTES.PORTAL.VERIFICATION_CONFIRMED(draft.id));
      } else if (draft.status === "PAYMENT_PENDING" || draft.status === "SUBMITTED") {
        setStep(3);
      }
      return;
    }
    if (draft.draftPayload && Object.keys(draft.draftPayload).length > 0 && draft.tier) {
      setStep((s) => (s === 0 ? 1 : s));
    }
  }, [draft, router]);

  if (isLoading || !draft) {
    return (
      <div className="text-sm py-12 text-center" style={{ color: "var(--brand-on-surface-variant)" }}>
        Loading…
      </div>
    );
  }

  const handleProperty = async (values: PropertyStepValues) => {
    try {
      setErrorMessage(null);
      await saveDraft.mutateAsync({
        step: 1,
        payload: {
          source: values.source,
          sourceUrl: values.sourceUrl,
          propertyType: values.propertyType,
          state: values.state,
          lga: values.lga,
          addressLine: values.addressLine,
          landmarkDescription: values.landmarkDescription,
          details: values.details,
          sellerInfo: values.sellerInfo,
        },
      });
      setStep(1);
    } catch (e) {
      setErrorMessage(getErrorMessage(e));
    }
  };

  const handleTier = async (tier: VerificationTier, currency: string) => {
    try {
      setErrorMessage(null);
      await selectTier.mutateAsync({ tier, currency });
      setStep(2);
    } catch (e) {
      setErrorMessage(getErrorMessage(e));
    }
  };

  const handleConsents = async (
    consents: { documentType: string; consentVersion: string }[],
  ) => {
    try {
      setErrorMessage(null);
      await submitVerification.mutateAsync(consents);
      setStep(3);
    } catch (e) {
      setErrorMessage(getErrorMessage(e));
    }
  };

  const handlePaid = (_paymentId: string) => {
    router.push(ROUTES.PORTAL.VERIFICATION_CONFIRMED(draft.id));
  };

  const tierIntent = (() => {
    const t = (searchParams.get("tier") ?? "").toLowerCase();
    return TIER_PARAM_MAP[t];
  })();

  const detailsAreUnknown = (() => {
    const d = (draft.draftPayload as any)?.details;
    if (!d) return false;
    return d.cOfOStatus === "UNKNOWN" || d.surveyPlanStatus === "UNKNOWN";
  })();

  return (
    <div className="max-w-3xl mx-auto px-4 py-10 space-y-8">
      <header className="space-y-2">
        <span
          className="inline-block text-xs font-medium uppercase tracking-wider px-2.5 py-1 rounded-full"
          style={{
            color: "var(--brand-viridian)",
            backgroundColor: "var(--brand-viridian-xlight)",
          }}
        >
          Verification {draft.vid}
        </span>
        <h1
          className="text-3xl sm:text-4xl font-semibold tracking-tight"
          style={{ color: "var(--brand-navy)", fontFamily: "var(--font-display, Manrope)" }}
        >
          Submit a property
        </h1>
      </header>

      <Stepper steps={STEPS} current={step} />

      <section
        className="rounded-2xl p-6 sm:p-8"
        style={{
          backgroundColor: "var(--brand-surface-card)",
          boxShadow: "0px 24px 48px rgba(0,13,34,0.06)",
        }}
      >
        {errorMessage && (
          <div
            className="text-sm mb-4 rounded-md p-3"
            style={{
              color: "var(--destructive)",
              backgroundColor: "rgba(186,26,26,0.06)",
            }}
          >
            {errorMessage}
          </div>
        )}

        {step === 0 && (
          <PropertyStep
            defaultValues={(draft.draftPayload as Partial<PropertyStepValues>) ?? undefined}
            pending={saveDraft.isPending}
            onSubmit={handleProperty}
          />
        )}
        {step === 1 && (
          <TierStep
            initial={tierIntent ?? draft.tier ?? "STANDARD"}
            pending={selectTier.isPending}
            recommendUpgrade={detailsAreUnknown}
            onBack={() => setStep(0)}
            onSubmit={handleTier}
          />
        )}
        {step === 2 && (
          <ConsentStep
            pending={submitVerification.isPending}
            onBack={() => setStep(1)}
            onSubmit={handleConsents}
          />
        )}
        {step === 3 && (
          <PaymentStep verification={draft} onPaid={handlePaid} />
        )}
      </section>
    </div>
  );
}
