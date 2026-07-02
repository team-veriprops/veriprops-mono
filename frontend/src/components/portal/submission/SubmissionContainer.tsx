"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@3rdparty/ui/button";
import { toast } from "@components/3rdparty/ui/use-toast";
import WizardOverlay from "@components/ui/wizard/WizardOverlay";
import { ROUTES } from "@lib/routes";
import {
  useCreateDraftMutation,
  useSaveDraftMutation,
  useSubmitVerificationMutation,
  useVerificationTermsQuery,
} from "@components/portal/libs/useVerificationQueries";
import { SubmitVerificationRequest } from "@/types/verification";
import { EMPTY_SUBMISSION, SUBMISSION_STEPS, SubmissionState } from "./types";
import { canAdvanceSubmissionStep } from "./validation";
import PropertyStep from "./PropertyStep";
import TierStep from "./TierStep";
import ConsentStep from "./ConsentStep";

const LAST_IN_WIZARD_STEP = 2; // Consent — "Continue to Payment" submits + routes to /pay.

export default function SubmissionContainer() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [state, setState] = useState<SubmissionState>(EMPTY_SUBMISSION);
  const [verificationId, setVerificationId] = useState<string | null>(null);
  // Generated once in the mount effect (below), not during render — the create
  // call is idempotent on this client key, so a refresh won't create a duplicate.
  const idempotencyKey = useRef<string>("");
  const created = useRef(false);

  const createDraft = useCreateDraftMutation();
  const saveDraft = useSaveDraftMutation();
  const submit = useSubmitVerificationMutation();
  const { data: terms } = useVerificationTermsQuery();

  // VID/DRAFT created on step-1 load (idempotent on the client key → no dup on refresh).
  useEffect(() => {
    if (created.current) return;
    created.current = true;
    idempotencyKey.current =
      typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : String(Date.now());
    createDraft.mutateAsync(idempotencyKey.current).then((res) => {
      if (res.data) setVerificationId(res.data.id);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const update = (patch: Partial<SubmissionState>) => setState((s) => ({ ...s, ...patch }));
  const updateProperty = (patch: Partial<SubmissionState["property"]>) =>
    setState((s) => ({ ...s, property: { ...s.property, ...patch } }));

  const persist = (nextStep: number, nextState: SubmissionState) => {
    if (verificationId) {
      saveDraft.mutate({
        id: verificationId,
        step: nextStep,
        payload: nextState as unknown as Record<string, unknown>,
      });
    }
  };

  const goNext = async () => {
    if (step < LAST_IN_WIZARD_STEP) {
      const next = step + 1;
      setStep(next);
      persist(next, state);
      return;
    }
    // Consent → submit → payment overlay.
    if (!verificationId) return;
    const payload: SubmitVerificationRequest = {
      property: {
        propertyType: state.property.propertyType,
        address: state.property.address || undefined,
        landmark: state.property.landmark || undefined,
        state: state.property.state || undefined,
        latitude: state.property.latitude,
        longitude: state.property.longitude,
        placeId: state.property.placeId,
      },
      tier: state.tier,
      currency: state.currency,
      consent: { consentVersion: terms?.consentVersion ?? "1.0.0" },
    };
    try {
      await submit.mutateAsync({ id: verificationId, payload });
      router.push(ROUTES.PORTAL.VERIFICATION_PAY(verificationId));
    } catch {
      toast({ title: "Could not submit", description: "Please try again.", variant: "destructive" });
    }
  };

  const goBack = () => setStep((s) => Math.max(0, s - 1));
  const close = () => router.push(ROUTES.PORTAL.VERIFICATIONS);

  const footer = (
    <>
      <Button variant="ghost" onClick={goBack} disabled={step === 0} data-testid="verify-new-back">
        Back
      </Button>
      <Button
        onClick={goNext}
        disabled={!canAdvanceSubmissionStep(step, state) || submit.isPending || !verificationId}
        data-testid="verify-new-continue"
      >
        {step === LAST_IN_WIZARD_STEP ? "Continue to Payment" : "Continue"}
      </Button>
    </>
  );

  return (
    <WizardOverlay
      steps={SUBMISSION_STEPS}
      current={step}
      onClose={close}
      title="New Verification"
      footer={footer}
      testIdPrefix="verify-new"
    >
      {step === 0 && <PropertyStep value={state.property} onChange={updateProperty} />}
      {step === 1 && (
        <TierStep tier={state.tier} currency={state.currency} onChange={update} />
      )}
      {step === 2 && (
        <ConsentStep
          accepted={state.consentAccepted}
          onAcceptedChange={(v) => update({ consentAccepted: v })}
          termsVersion={terms?.consentVersion}
        />
      )}
    </WizardOverlay>
  );
}
