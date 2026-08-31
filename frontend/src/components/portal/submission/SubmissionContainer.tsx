"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@3rdparty/ui/button";
import { toast } from "@components/3rdparty/ui/use-toast";
import WizardOverlay from "@components/ui/wizard/WizardOverlay";
import { ROUTES } from "@lib/routes";
import {
  useCreateDraftMutation,
  useResumableDraftQuery,
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
  // Generated once inside startDraft, not during render — the create call is
  // idempotent on this client key, so a refresh won't create a duplicate.
  const idempotencyKey = useRef<string>("");
  // Guards startDraft() from firing twice (resumed drafts never need it at all).
  const draftStartRequested = useRef(false);
  // Guards the resumable-draft mount decision (resume vs. wait-for-dirty) from re-running.
  const resumeChecked = useRef(false);
  // Has the customer changed anything from EMPTY_SUBMISSION yet — staging only begins once true.
  const dirtiedRef = useRef(false);
  const [draftFailed, setDraftFailed] = useState(false);

  const createDraft = useCreateDraftMutation();
  const saveDraft = useSaveDraftMutation();
  const submit = useSubmitVerificationMutation();
  const { data: terms } = useVerificationTermsQuery();
  const { data: resumable } = useResumableDraftQuery();

  // VID/DRAFT created on first dirty change (idempotent on the client key → no dup on refresh).
  const startDraft = () => {
    if (draftStartRequested.current) return;
    draftStartRequested.current = true;
    setDraftFailed(false);
    if (!idempotencyKey.current) {
      idempotencyKey.current =
        typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : String(Date.now());
    }
    createDraft
      .mutateAsync(idempotencyKey.current)
      .then((res) => {
        if (res.data) setVerificationId(res.data.id);
        else {
          setDraftFailed(true);
          draftStartRequested.current = false;
        }
      })
      .catch(() => {
        setDraftFailed(true);
        draftStartRequested.current = false;
      });
  };

  // Silent auto-resume (§ can't start a second unpaid verification): once the
  // read-only resumable check settles (its query never leaves `data` undefined
  // past the initial fetch — a failed check resolves to `null`), either hydrate
  // the existing dirtied draft directly, or — if the customer already typed
  // something while it was loading — start staging immediately. Otherwise
  // staging waits for the first dirty change (below), never firing for an
  // untouched, abandoned wizard.
  useEffect(() => {
    if (resumable === undefined || resumeChecked.current || !resumable) return;
    resumeChecked.current = true;
    draftStartRequested.current = true; // already have a draft id — startDraft must never fire
    setVerificationId(resumable.id);
    // If the customer already started typing before this check resolved, keep their
    // input and current step — just the id above so saves target the existing draft.
    if (dirtiedRef.current) return;
    setStep(Math.min(resumable.step, LAST_IN_WIZARD_STEP));
    setState((s) => ({ ...s, ...(resumable.payload as Partial<SubmissionState>) }));
  }, [resumable]);

  // Nothing to resume — either wait for the first dirty change (below), or, if the
  // customer already typed something while the resumable check was loading, start now.
  useEffect(() => {
    if (resumable === undefined || resumable || resumeChecked.current) return;
    resumeChecked.current = true;
    if (dirtiedRef.current) startDraft();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resumable]);

  const update = (patch: Partial<SubmissionState>) => {
    setState((s) => ({ ...s, ...patch }));
    dirtiedRef.current = true;
    if (resumeChecked.current) startDraft();
  };
  const updateProperty = (patch: Partial<SubmissionState["property"]>) => {
    setState((s) => ({ ...s, property: { ...s.property, ...patch } }));
    dirtiedRef.current = true;
    if (resumeChecked.current) startDraft();
  };

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
    const detailEntries = Object.entries(state.property.details).filter(([, v]) => v);
    const payload: SubmitVerificationRequest = {
      property: {
        propertyType: state.property.propertyType,
        address: state.property.address || undefined,
        landmark: state.property.landmark || undefined,
        state: state.property.state || undefined,
        latitude: state.property.latitude,
        longitude: state.property.longitude,
        placeId: state.property.placeId,
        details: detailEntries.length ? Object.fromEntries(detailEntries) : undefined,
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
      {draftFailed && (
        <div
          className="mb-4 flex items-center justify-between gap-3 rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm"
          data-testid="verify-new-draft-error"
        >
          <span className="text-destructive">
            We couldn&apos;t start your verification. Please check your connection and retry.
          </span>
          <Button size="sm" variant="outline" onClick={startDraft} disabled={createDraft.isPending}>
            Retry
          </Button>
        </div>
      )}
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
