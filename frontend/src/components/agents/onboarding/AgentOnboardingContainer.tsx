"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@3rdparty/ui/button";
import { toast } from "@components/3rdparty/ui/use-toast";
import WizardOverlay from "@components/ui/wizard/WizardOverlay";
import { ROUTES } from "@lib/routes";
import { AgentApplicationStatus, AgentRole, SubmitAgentApplicationRequest } from "@/types/agent";
import {
  useAgentDraftQuery,
  useAgentStatusQuery,
  useAgentTermsQuery,
  useSaveAgentDraftMutation,
  useSubmitAgentApplicationMutation,
} from "@components/agents/libs/useAgentQueries";
import { useAuthStore } from "@components/website/auth/libs/useAuthStore";
import { useRefreshSession } from "@components/website/auth/libs/useAuthQueries";
import { UserPersona } from "@components/website/auth/models";
import { navigateAfterPersonaChange } from "@lib/session-navigation";
import { onboardingExitHref } from "./exit";
import { AGENT_WIZARD_STEPS, AgentWizardState, EMPTY_WIZARD_STATE } from "./types";
import { canAdvanceStep, canSubmit } from "./validation";
import RolesStep from "./RolesStep";
import KycStep from "./KycStep";
import CredentialsStep from "./CredentialsStep";
import ReviewStep from "./ReviewStep";

interface AgentOnboardingContainerProps {
  /** False for the compulsory login-time gate (no application yet / REJECTED) — hides the close control. */
  closable?: boolean;
}

export default function AgentOnboardingContainer({ closable = true }: AgentOnboardingContainerProps) {
  const router = useRouter();
  const refreshSession = useRefreshSession();
  const personas = (useAuthStore((s) => s.session)?.user?.personas ?? []) as UserPersona[];
  const [step, setStep] = useState(0);
  const [state, setState] = useState<AgentWizardState>(EMPTY_WIZARD_STATE);
  const [termsAccepted, setTermsAccepted] = useState(false);
  const restored = useRef(false);

  const { data: draft } = useAgentDraftQuery();
  const { data: terms } = useAgentTermsQuery();
  const { data: status } = useAgentStatusQuery();
  const saveDraft = useSaveAgentDraftMutation();
  const submit = useSubmitAgentApplicationMutation();

  // A rejected applicant is sent back through this same wizard (§3.1). Without the reason they
  // were given, the only thing they can do is submit the identical application again.
  const rejectionReason =
    status?.status === AgentApplicationStatus.REJECTED ? status.rejectionReason : undefined;

  // Restore a saved draft once (refresh/relogin resumes at the saved step).
  useEffect(() => {
    if (restored.current || !draft) return;
    restored.current = true;
    setState({ ...EMPTY_WIZARD_STATE, ...(draft.payload as Partial<AgentWizardState>) });
    setStep(Math.min(draft.step, AGENT_WIZARD_STEPS.length - 1));
  }, [draft]);

  const update = (patch: Partial<AgentWizardState>) => setState((s) => ({ ...s, ...patch }));

  const persist = (nextStep: number, nextState: AgentWizardState) => {
    saveDraft.mutate({ step: nextStep, payload: nextState as unknown as Record<string, unknown> });
  };

  // Closing returns a customer to their own portal; an applicant with no other surface has
  // nowhere to go, which is what the compulsory gate (`closable={false}`) already reflects.
  const close = () => router.push(onboardingExitHref(personas));

  const goNext = () => {
    const next = Math.min(step + 1, AGENT_WIZARD_STEPS.length - 1);
    setStep(next);
    persist(next, state);
  };

  const goBack = () => setStep((s) => Math.max(0, s - 1));

  const onSubmit = async () => {
    if (!canSubmit(state, termsAccepted)) return;
    const payload: SubmitAgentApplicationRequest = {
      roles: state.roles,
      kyc: state.kyc,
      credentials: state.credentials,
      coverage: state.coverage,
      bio: state.bio || undefined,
      yearsExperience: state.yearsExperience,
      truthfulnessConfirmed: state.truthfulnessConfirmed,
      agentTermsVersion: terms?.consentVersion ?? "1.0.0",
    };
    try {
      await submit.mutateAsync(payload);
      toast({ title: "Application submitted", description: "We'll review it and get back to you." });
      // Submitting granted the AGENT persona and the backend rotated the session with it, so this
      // browser's whole picture of who it belongs to is a step behind — including the router's
      // cached prefetches, every one of which the route guard turned away before the grant. The
      // stored session is refreshed first because it is persisted and would otherwise survive the
      // reload still claiming one hat.
      await refreshSession();
      navigateAfterPersonaChange(ROUTES.AGENT.DASHBOARD);
    } catch {
      toast({ title: "Submission failed", description: "Please try again.", variant: "destructive" });
    }
  };

  const isLast = step === AGENT_WIZARD_STEPS.length - 1;
  const submitting = submit.isPending;

  const footer = (
    <>
      <Button variant="ghost" onClick={goBack} disabled={step === 0} data-testid="agent-apply-back">
        Back
      </Button>
      {isLast ? (
        <Button
          onClick={onSubmit}
          disabled={submitting || !canSubmit(state, termsAccepted)}
          data-testid="agent-apply-submit"
        >
          {submitting ? "Submitting…" : "Submit application"}
        </Button>
      ) : (
        <Button onClick={goNext} disabled={!canAdvanceStep(step, state)} data-testid="agent-apply-continue">
          Continue
        </Button>
      )}
    </>
  );

  return (
    <WizardOverlay
      steps={AGENT_WIZARD_STEPS}
      current={step}
      onClose={close}
      title="Become a Verified Agent"
      footer={footer}
      testIdPrefix="agent-apply"
      closable={closable}
    >
      {rejectionReason && (
        <div
          className="mb-6 rounded-lg border border-destructive/40 bg-destructive/5 p-4 text-sm"
          data-testid="agent-apply-rejection-reason"
        >
          <span className="font-medium text-destructive">
            Your last application was not approved:{" "}
          </span>
          {rejectionReason}
        </div>
      )}

      {step === 0 && <RolesStep value={state.roles} onChange={(roles: AgentRole[]) => update({ roles })} />}
      {step === 1 && <KycStep value={state.kyc} onChange={(kyc) => update({ kyc })} />}
      {step === 2 && <CredentialsStep state={state} update={update} />}
      {step === 3 && (
        <ReviewStep
          state={state}
          update={update}
          termsAccepted={termsAccepted}
          onTermsAcceptedChange={setTermsAccepted}
          termsVersion={terms?.consentVersion}
        />
      )}
    </WizardOverlay>
  );
}
