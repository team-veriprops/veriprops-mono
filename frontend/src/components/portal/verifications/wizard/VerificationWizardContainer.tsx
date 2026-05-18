"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Stepper from "./Stepper";
import TypeSourceStep, { TypeSourceStepValues } from "./TypeSourceStep";
import LocationStep, { LocationStepValues } from "./LocationStep";
import DetailsStep, { DetailsStepValues } from "./DetailsStep";
import TierStep from "../pricing/TierStep";
import ConsentStep from "./ConsentStep";
import PaymentStep from "../payment/PaymentStep";
import {
  useActiveDraft,
  useSaveDraftMutation,
  useSelectTierMutation,
  useSubmitVerificationMutation,
} from "../libs/useVerificationQueries";
import type { PropertyType, VerificationTier } from "../libs/verification-service";
import { ROUTES } from "@lib/routes";
import { getErrorMessage } from "@lib/utils";

// Step indices
const STEP_TYPE = 0;
const STEP_LOCATION = 1;
const STEP_DETAILS = 2;
const STEP_TIER = 3;
const STEP_CONSENT = 4;
const STEP_PAYMENT = 5;

const STEPS = ["Property", "Location", "Details", "Pricing", "Payment"];

const TIER_PARAM_MAP: Record<string, VerificationTier> = {
  basic: "BASIC",
  standard: "STANDARD",
  premium: "PREMIUM",
};

export default function VerificationWizardContainer() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { data: draft, isLoading } = useActiveDraft();
  const [step, setStep] = useState(STEP_TYPE);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Local state collected across steps 0-2 (not sent to backend until step 2 completes)
  const [typeSource, setTypeSource] = useState<TypeSourceStepValues | null>(null);
  const [locationValues, setLocationValues] = useState<LocationStepValues | null>(null);

  const verificationId = draft?.id ?? "";
  const saveDraft = useSaveDraftMutation(verificationId);
  const selectTier = useSelectTierMutation(verificationId);
  const submitVerification = useSubmitVerificationMutation(verificationId);

  // Resume — cap at Tier step (index 3). Consent + Payment are always re-entered.
  useEffect(() => {
    if (!draft) return;
    if (draft.status !== "DRAFT") {
      if (draft.status === "PAID" || draft.status === "IN_PROGRESS") {
        router.replace(ROUTES.PORTAL.VERIFICATION_CONFIRMED(draft.id));
      } else if (draft.status === "PAYMENT_PENDING" || draft.status === "SUBMITTED") {
        setStep(STEP_PAYMENT);
      }
      return;
    }
    if (draft.draftPayload && Object.keys(draft.draftPayload).length > 0 && draft.tier) {
      setStep((s) => (s < STEP_TIER ? STEP_TIER : s));
    }
  }, [draft, router]);

  if (isLoading || !draft) {
    return (
      <div className="text-sm py-12 text-center" style={{ color: "var(--brand-on-surface-variant)" }}>
        Loading…
      </div>
    );
  }

  // Step 0: TypeSource — advance to Location immediately on selection
  const handleTypeSource = (values: TypeSourceStepValues) => {
    setTypeSource(values);
    setStep(STEP_LOCATION);
  };

  // Step 1: Location — just store locally, advance to Details
  const handleLocation = (values: LocationStepValues) => {
    setLocationValues(values);
    setStep(STEP_DETAILS);
  };

  // Step 2: Details — combine all local data + send to backend
  const handleDetails = async (values: DetailsStepValues) => {
    try {
      setErrorMessage(null);
      const ts = typeSource ?? { propertyType: "LAND" as PropertyType, source: "MANUAL" as const };
      const loc = locationValues ?? { state: "LAGOS", landmarkDescription: "" };

      await saveDraft.mutateAsync({
        step: 1,
        payload: {
          source: ts.source,
          sourceUrl: ts.sourceUrl,
          propertyType: ts.propertyType,
          state: loc.state,
          lga: loc.lga,
          addressLine: loc.addressLine,
          lat: loc.lat,
          lng: loc.lng,
          landmarkDescription: loc.landmarkDescription,
          details: values.details,
          sellerInfo: values.sellerInfo,
          estimatedPriceMinor: values.estimatedPriceMinor,
          estimatedPriceCurrency: values.estimatedPriceCurrency,
        },
      });
      setStep(STEP_TIER);
    } catch (e) {
      setErrorMessage(getErrorMessage(e as Error));
    }
  };

  const handleTier = async (tier: VerificationTier, currency: string) => {
    try {
      setErrorMessage(null);
      await selectTier.mutateAsync({ tier, currency });
      setStep(STEP_CONSENT);
    } catch (e) {
      setErrorMessage(getErrorMessage(e as Error));
    }
  };

  const handleConsents = async (
    consents: { documentType: string; consentVersion: string }[],
  ) => {
    try {
      setErrorMessage(null);
      await submitVerification.mutateAsync(consents);
      setStep(STEP_PAYMENT);
    } catch (e) {
      setErrorMessage(getErrorMessage(e as Error));
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

  const propertyType: PropertyType =
    (typeSource?.propertyType ??
      (draft.draftPayload as any)?.propertyType ??
      "LAND") as PropertyType;

  // Stepper only shows steps 0-4 (5 steps, consent+payment share step 4 slot)
  const stepperIndex = Math.min(step, STEP_CONSENT);

  return (
    <div className="max-w-3xl mx-auto px-4 py-10 space-y-8">
      <header className="space-y-2">
        <span
          className="inline-block text-xs font-medium uppercase tracking-wider px-2.5 py-1 rounded-full"
          style={{ color: "var(--brand-viridian)", backgroundColor: "var(--brand-viridian-xlight)" }}
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

      <Stepper steps={STEPS} current={stepperIndex} />

      <section
        className="rounded-2xl p-6 sm:p-8"
        style={{ backgroundColor: "var(--brand-surface-card)", boxShadow: "0px 24px 48px rgba(0,13,34,0.06)" }}
      >
        {errorMessage && (
          <div
            className="text-sm mb-4 rounded-md p-3"
            style={{ color: "var(--destructive)", backgroundColor: "rgba(186,26,26,0.06)" }}
          >
            {errorMessage}
          </div>
        )}

        {step === STEP_TYPE && (
          <TypeSourceStep
            defaultValues={typeSource ?? undefined}
            onSubmit={handleTypeSource}
          />
        )}

        {step === STEP_LOCATION && (
          <LocationStep
            defaultValues={locationValues ?? undefined}
            pending={false}
            onBack={() => setStep(STEP_TYPE)}
            onSubmit={handleLocation}
          />
        )}

        {step === STEP_DETAILS && (
          <DetailsStep
            propertyType={propertyType}
            defaultValues={undefined}
            pending={saveDraft.isPending}
            onBack={() => setStep(STEP_LOCATION)}
            onSubmit={handleDetails}
          />
        )}

        {step === STEP_TIER && (
          <TierStep
            initial={tierIntent ?? draft.tier ?? "STANDARD"}
            pending={selectTier.isPending}
            recommendUpgrade={detailsAreUnknown}
            onBack={() => setStep(STEP_DETAILS)}
            onSubmit={handleTier}
          />
        )}

        {step === STEP_CONSENT && (
          <ConsentStep
            pending={submitVerification.isPending}
            onBack={() => setStep(STEP_TIER)}
            onSubmit={handleConsents}
          />
        )}

        {step === STEP_PAYMENT && (
          <PaymentStep verification={draft} onPaid={handlePaid} />
        )}
      </section>
    </div>
  );
}
