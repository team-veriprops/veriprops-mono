"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import AuthShell from "../AuthShell";
import AuthHeading from "../AuthHeading";
import SocialAuthButtons, { AuthDivider } from "../SocialAuthButtons";
import Stepper from "./Stepper";
import AccountBasicsStep from "./AccountBasicsStep";
import VerifyEmailPhoneStep from "./VerifyEmailPhoneStep";
import ResidenceStep from "./ResidenceStep";
import ConsentStep from "./ConsentStep";
import { authService, useSignupMutation } from "../libs/useAuthQueries";
import type { VerifyStepValues } from "./VerifyEmailPhoneStep";
import {
  SignupStep1Values,
  SignupStep2Values,
  SignupStep3Values,
} from "../schemas";
import { UserConsent, SignupDraft } from "@components/website/auth/models";
import {
  loadActiveLocalDraft,
  loadLocalDraft,
  saveLocalDraft,
  clearLocalDraft,
} from "../libs/signupDraft";
import { ROUTES, isAuthIntent } from "@lib/routes";
import { resolvePostAuthRedirect } from "@components/website/auth/libs/auth/redirect";
import { getDeviceFingerprint } from "@components/website/auth/libs/auth/fingerprint";
import { getErrorMessage } from "@lib/utils";

const STEPS = ["Account", "Verify", "Residence", "Consent"];

interface DraftPayload extends Partial<SignupStep1Values & SignupStep2Values & SignupStep3Values> {}

export default function SignupContainer() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const intentParam = searchParams.get("intent");
  const intent = isAuthIntent(intentParam) ? intentParam : "default";
  const tier = searchParams.get("tier");
  const redirect = searchParams.get("redirect");

  const [step, setStep] = useState(0);
  const [step1, setStep1] = useState<SignupStep1Values | null>(null);
  const [step2, setStep2] = useState<SignupStep2Values | null>(null);
  const [step3, setStep3] = useState<SignupStep3Values | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [resumed, setResumed] = useState(false);

  const signupMutation = useSignupMutation();

  // Restore draft on mount: server takes precedence (cross-device), with
  // localStorage as the offline mirror.
  useEffect(() => {
    let cancelled = false;
    const applyDraft = (draft: SignupDraft) => {
      const payload = draft.payload as DraftPayload;
      if (payload.email) {
        setStep1({
          firstName: payload.firstName ?? "",
          lastName: payload.lastName ?? "",
          email: payload.email,
          password: payload.password ?? "",
        } as SignupStep1Values);
      }
      if (payload.emailVerified && payload.phoneVerified) {
        setStep2({
          countryCode: payload.countryCode ?? "NG",
          dialCode: payload.dialCode ?? "+234",
          phone: payload.phone ?? "",
          emailVerified: true,
          phoneVerified: true,
        });
      }
      if (payload.countryOfResidence) {
        setStep3({
          countryOfResidence: payload.countryOfResidence,
          timezone: payload.timezone!,
          preferredCurrency: payload.preferredCurrency!,
        });
      }
      setStep(Math.max(0, Math.min(STEPS.length - 1, draft.step)));
      setResumed(true);
    };

    const localDraft = loadActiveLocalDraft();
    (async () => {
      // Try server first when we know the email (from a local mirror). If the
      // server has a fresher copy, apply that; otherwise fall back to local.
      if (localDraft?.email) {
        try {
          const res = await authService.getSignupDraft(localDraft.email);
          const remote = res.data;
          if (cancelled) return;
          if (remote && remote.updatedAt >= localDraft.updatedAt) {
            applyDraft(remote);
            return;
          }
        } catch {
          // Server unavailable — local mirror is the next-best thing.
        }
        if (!cancelled) applyDraft(localDraft);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const persistDraft = (next: { step: number; payload: DraftPayload }) => {
    if (!next.payload.email) return;
    const draft: SignupDraft = {
      email: next.payload.email,
      step: next.step,
      payload: next.payload,
      updatedAt: new Date().toISOString(),
    };
    saveLocalDraft(draft);
    // Fire-and-forget server sync. Non-fatal: localStorage is sufficient for
    // resume-on-same-device, server adds cross-device resume.
    authService
      .saveSignupDraft(draft)
      .catch(() => { /* tolerate offline / first-load */ });
  };

  const handleStep1 = (values: SignupStep1Values) => {
    setStep1(values);
    persistDraft({ step: 1, payload: { ...values } });
    setStep(1);
  };

  const handleStep2 = (values: VerifyStepValues) => {
    // verifyFormSchema enforces both verified flags via .refine — by the time we
    // get here, emailVerified === phoneVerified === true. Narrow accordingly.
    const next: SignupStep2Values = {
      countryCode: values.countryCode,
      dialCode: values.dialCode,
      phone: values.phone,
      emailVerified: true,
      phoneVerified: true,
    };
    setStep2(next);
    persistDraft({
      step: 2,
      payload: { ...(step1 ?? {}), ...next } as DraftPayload,
    });
    setStep(2);
  };

  const handleStep3 = (values: SignupStep3Values) => {
    setStep3(values);
    persistDraft({
      step: 3,
      payload: { ...(step1 ?? {}), ...(step2 ?? {}), ...values } as DraftPayload,
    });
    setStep(3);
  };

  const handleConsent = async (consents: UserConsent[]) => {
    if (!step1 || !step2 || !step3) return;
    setErrorMessage(null);

    try {
      const result = await signupMutation.mutateAsync({
        firstName: step1.firstName,
        lastName: step1.lastName,
        email: step1.email,
        password: step1.password,
        countryCode: step2.countryCode,
        dialCode: step2.dialCode,
        phone: step2.phone,
        countryOfResidence: step3.countryOfResidence,
        timezone: step3.timezone,
        preferredCurrency: step3.preferredCurrency,
        consents,
        intent,
        deviceFingerprint: getDeviceFingerprint(),
      });

      clearLocalDraft(step1.email);
      authService.discardSignupDraft(step1.email).catch(() => undefined);

      const user = result.data?.user;
      const dest = user
        ? resolvePostAuthRedirect(user, { intent, redirect })
        : ROUTES.PORTAL.DASHBOARD;
      router.push(dest);
    } catch (err) {
      setErrorMessage(
        getErrorMessage(
          err as Error,
          "We couldn't create your account. Please try again or contact support.",
        ),
      );
    }
  };

  const subtitle =
    intent === "agent"
      ? "Create your Veriprops account first. After this, we'll walk you through the agent application."
      : tier
      ? `Set up your account so we can pre-select the ${tier} tier on your verification.`
      : "It takes about 2 minutes. We verify your email and phone before we let you submit a property.";

  return (
    <AuthShell>
      <AuthHeading
        eyebrow={intent === "agent" ? "Step 1 of 2 — agent path" : "Create your account"}
        title="Welcome to Veriprops."
        subtitle={subtitle}
      />

      <Stepper steps={STEPS} current={step} className="mb-8" />

      {step === 0 && (
        <>
          <AccountBasicsStep defaultValues={step1 ?? undefined} onSubmit={handleStep1} />
          <AuthDivider />
          <SocialAuthButtons verb="Sign up with" intent={intent} />
        </>
      )}

      {step === 1 && step1 && (
        <VerifyEmailPhoneStep
          defaults={{
            email: step1.email,
            countryCode: step2?.countryCode,
            dialCode: step2?.dialCode,
            phone: step2?.phone,
          }}
          onSubmit={handleStep2}
          onBack={() => setStep(0)}
        />
      )}

      {step === 2 && (
        <ResidenceStep
          defaultValues={step3 ?? undefined}
          onSubmit={handleStep3}
          onBack={() => setStep(1)}
        />
      )}

      {step === 3 && (
        <ConsentStep
          loading={signupMutation.isPending}
          errorMessage={errorMessage}
          onSubmit={handleConsent}
          onBack={() => setStep(2)}
        />
      )}

      {resumed && step > 0 && (
        <p
          className="mt-6 text-xs text-center"
          style={{ color: "var(--brand-on-surface-variant)" }}
        >
          We restored your previous progress.
        </p>
      )}

      <p className="mt-8 text-sm text-center" style={{ color: "var(--brand-on-surface-variant)" }}>
        Already have an account?{" "}
        <Link
          href={ROUTES.AUTH.LOGIN}
          className="font-semibold underline-offset-2 hover:underline"
          style={{ color: "var(--brand-navy)" }}
        >
          Sign in
        </Link>
      </p>
    </AuthShell>
  );
}

// Re-export for tests.
export { loadLocalDraft };
