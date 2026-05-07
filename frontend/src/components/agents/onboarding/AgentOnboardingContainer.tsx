"use client";

import { useEffect, useState } from "react";
import Stepper from "./Stepper";
import TypeSelectionStep from "./TypeSelectionStep";
import KycStep from "./KycStep";
import CredentialsStep from "./CredentialsStep";
import ReviewStep from "./ReviewStep";
import ApprovalStatusCard from "./ApprovalStatusCard";
import {
  useAgentApplication,
  useSaveCredentialsMutation,
  useSaveTypesStepMutation,
  useSubmitApplicationMutation,
  useUploadKycDocsMutation,
  useVerifyBvnMutation,
} from "../libs/useAgentApplicationQueries";
import type { AgentType } from "../libs/agent-service";
import { getErrorMessage } from "@lib/utils";
import { deriveResumeStep } from "./wizardUtils";

const STEPS = ["Roles", "KYC", "Credentials", "Review"];

export default function AgentOnboardingContainer() {
  const { data: application, isLoading } = useAgentApplication();
  const [step, setStep] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const saveTypes = useSaveTypesStepMutation();
  const verifyBvn = useVerifyBvnMutation();
  const uploadDocs = useUploadKycDocsMutation();
  const saveCredentials = useSaveCredentialsMutation();
  const submitApp = useSubmitApplicationMutation();

  // Resume the wizard at the right step based on persisted server state.
  useEffect(() => {
    if (!application) return;
    const resumeAt = deriveResumeStep(application);
    setStep((s) => (s === 0 ? resumeAt : s));
  }, [application]);

  if (isLoading || !application) {
    return (
      <div
        className="text-sm py-12 text-center"
        style={{ color: "var(--brand-on-surface-variant)" }}
      >
        Loading…
      </div>
    );
  }

  if (application.status !== "DRAFT") {
    return <ApprovalStatusCard application={application} />;
  }

  const handleTypes = async (types: AgentType[]) => {
    try {
      setErrorMessage(null);
      await saveTypes.mutateAsync({ types });
      setStep(1);
    } catch (e) {
      setErrorMessage(getErrorMessage(e));
    }
  };

  const handleVerifyBvn = async (bvn: string) => {
    try {
      setErrorMessage(null);
      const res = await verifyBvn.mutateAsync({ bvn });
      return res.data ?? null;
    } catch (e) {
      setErrorMessage(getErrorMessage(e));
      return null;
    }
  };

  const handleUploadDocs = async (req: {
    idDocType: import("../libs/agent-service").IdDocType;
    idDocUrl: string;
    selfieUrl: string;
  }) => {
    try {
      setErrorMessage(null);
      await uploadDocs.mutateAsync(req);
    } catch (e) {
      setErrorMessage(getErrorMessage(e));
    }
  };

  const handleCredentials = async (
    req: import("../libs/agent-service").CredentialsStepRequest,
  ) => {
    try {
      setErrorMessage(null);
      await saveCredentials.mutateAsync(req);
      setStep(3);
    } catch (e) {
      setErrorMessage(getErrorMessage(e));
    }
  };

  const handleSubmit = async (req: {
    truthfulnessAcknowledged: boolean;
    agentTermsConsentVersion: string;
  }) => {
    try {
      setErrorMessage(null);
      await submitApp.mutateAsync(req);
      // Status flips to PENDING — the rendered branch above will switch.
    } catch (e) {
      setErrorMessage(getErrorMessage(e));
    }
  };

  return (
    <div className="max-w-3xl mx-auto px-4 py-10 space-y-8">
      <header className="space-y-3">
        <span
          className="inline-block text-xs font-medium uppercase tracking-wider px-2.5 py-1 rounded-full"
          style={{
            color: "var(--brand-viridian)",
            backgroundColor: "var(--brand-viridian-xlight)",
          }}
        >
          Agent application
        </span>
        <h1
          className="text-3xl sm:text-4xl font-semibold tracking-tight"
          style={{ color: "var(--brand-navy)", fontFamily: "var(--font-display, Manrope)" }}
        >
          Become a verified Veriprops agent
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
          <TypeSelectionStep
            defaultValue={application.types}
            pending={saveTypes.isPending}
            onSubmit={handleTypes}
          />
        )}
        {step === 1 && (
          <KycStep
            application={application}
            onVerifyBvn={handleVerifyBvn}
            onUploadDocs={handleUploadDocs}
            onContinue={() => setStep(2)}
            onBack={() => setStep(0)}
            pending={verifyBvn.isPending || uploadDocs.isPending}
          />
        )}
        {step === 2 && (
          <CredentialsStep
            application={application}
            pending={saveCredentials.isPending}
            onBack={() => setStep(1)}
            onSubmit={handleCredentials}
          />
        )}
        {step === 3 && (
          <ReviewStep
            application={application}
            pending={submitApp.isPending}
            onBack={() => setStep(2)}
            onSubmit={handleSubmit}
          />
        )}
      </section>
    </div>
  );
}
