"use client";

import { useMemo, useState } from "react";
import { useHydrated } from "@hooks/useHydrated";
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
import { useSignupMutation } from "../libs/useAuthQueries";
import type { VerifyStepValues } from "./VerifyEmailPhoneStep";
import {
  SignupStep1Values,
  SignupStep2Values,
  SignupStep3Values,
} from "../schemas";
import { UserConsent, AuthIntent } from "@components/website/auth/models";
import {
  loadActiveLocalDraft,
  loadLocalDraft,
  saveLocalDraft,
  clearLocalDraft,
  type SignupDraftFields,
} from "../libs/signupDraft";
import { ROUTES, isAuthIntent } from "@lib/routes";
import { resolvePostAuthRedirect } from "@components/website/auth/libs/auth/redirect";
import { getDeviceFingerprint } from "@components/website/auth/libs/auth/fingerprint";
import { getErrorMessage } from "@lib/errors";
import { findCountry } from "@components/website/auth/libs/auth/locale";

const STEPS = ["Account", "Verify", "Residence", "Consent"];

export default function SignupContainer() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const intentParam = searchParams.get("intent");
  const intent = isAuthIntent(intentParam) ? intentParam : AuthIntent.DEFAULT;
  const tier = searchParams.get("tier");
  const redirect = searchParams.get("redirect");
  // §17.1 referral capture — an unknown code is ignored server-side, never blocks signup.
  const referralCode = searchParams.get("ref") ?? undefined;
  const emailParam = searchParams.get("email") ?? "";
  const firstNameParam = searchParams.get("firstName") ?? "";
  const lastNameParam = searchParams.get("lastName") ?? "";

  const [step, setStep] = useState(0);
  const [step1, setStep1] = useState<SignupStep1Values | null>(null);
  const [step2, setStep2] = useState<SignupStep2Values | null>(null);
  const [step3, setStep3] = useState<SignupStep3Values | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  // What this browser kept of an earlier, unfinished signup, read once hydrated (localStorage
  // is unavailable during SSR). It only ever pre-fills the forms: the signup resumes on
  // Account, the password is asked for again and the email/phone are verified again.
  const hydrated = useHydrated();
  const resumedDraft = useMemo(() => (hydrated ? loadActiveLocalDraft() : null), [hydrated]);
  const draftFields = resumedDraft?.fields;

  // Pre-populate step 1 from URL params (admin invite flow); only used when
  // there is no draft to restore.
  const urlStep1 = useMemo((): SignupStep1Values | null => {
    if (!emailParam) return null;
    return { email: emailParam, firstName: firstNameParam, lastName: lastNameParam, password: "" };
  }, [emailParam, firstNameParam, lastNameParam]);

  const draftStep1: SignupStep1Values | null = resumedDraft
    ? {
        firstName: draftFields?.firstName ?? "",
        lastName: draftFields?.lastName ?? "",
        email: draftFields?.email ?? resumedDraft.email,
        password: "",
      }
    : null;

  // Derive step 3 defaults from the phone country code chosen in step 2.
  // Left unmemoized (a plain derived value) — React Compiler auto-memoizes
  // this at build time, and a manual useMemo here couldn't agree with the
  // compiler's own (more precise) dependency inference.
  const step3Defaults = ((): Partial<SignupStep3Values> | undefined => {
    if (step3) return step3;
    if (draftFields?.countryOfResidence) {
      return {
        countryOfResidence: draftFields.countryOfResidence,
        timezone: draftFields.timezone,
        preferredCurrency: draftFields.preferredCurrency,
      };
    }
    if (!step2?.countryCode) return undefined;
    const info = findCountry(step2.countryCode);
    if (!info) return undefined;
    return {
      countryOfResidence: step2.countryCode,
      timezone: info.defaultTimezone,
      preferredCurrency: info.defaultCurrency,
    };
  })();

  const signupMutation = useSignupMutation();

  // `saveLocalDraft` keeps only the draft's allowlisted fields, so the password and the
  // verified flags in these step values never reach storage.
  const persistDraft = (fields: SignupDraftFields) => {
    if (fields.email) saveLocalDraft(fields.email, fields);
  };

  const handleStep1 = (values: SignupStep1Values) => {
    setStep1(values);
    persistDraft({ ...draftFields, ...values });
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
    persistDraft({ ...draftFields, ...step1, ...next });
    setStep(2);
  };

  const handleStep3 = (values: SignupStep3Values) => {
    setStep3(values);
    persistDraft({ ...draftFields, ...step1, ...step2, ...values });
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
        referralCode,
      });

      clearLocalDraft(step1.email);

      const user = result.data?.user;
      const dest = user
        ? resolvePostAuthRedirect(user, { intent, redirect })
        : ROUTES.PORTAL.DASHBOARD;
      router.push(dest);
    } catch (err) {
      setErrorMessage(
        getErrorMessage(
          err,
          "We couldn't create your account. Please try again or contact support.",
        ),
      );
    }
  };

  const subtitle =
    intent === AuthIntent.AGENT
      ? "Create your Veriprops account first. After this, we'll walk you through the agent application."
      : tier
      ? `Set up your account so we can pre-select the ${tier} tier on your verification.`
      : "It takes about 2 minutes. We verify your email and phone before we let you submit a property.";

  return (
    <AuthShell>
      <AuthHeading
        eyebrow={intent === AuthIntent.AGENT ? "Step 1 of 2 — agent path" : "Create your account"}
        title="Welcome to Veriprops."
        subtitle={subtitle}
      />

      <Stepper steps={STEPS} current={step} className="mb-8" />

      {step === 0 && (
        <>
          {/* Keyed on the restore so the form re-reads its defaults once the draft loads. */}
          <AccountBasicsStep
            key={resumedDraft ? "resumed" : "fresh"}
            defaultValues={step1 ?? draftStep1 ?? urlStep1 ?? undefined}
            onSubmit={handleStep1}
          />
          <AuthDivider />
          <SocialAuthButtons verb="Sign up with" intent={intent} />
        </>
      )}

      {step === 1 && step1 && (
        <VerifyEmailPhoneStep
          defaults={{
            email: step1.email,
            countryCode: step2?.countryCode ?? draftFields?.countryCode,
            dialCode: step2?.dialCode ?? draftFields?.dialCode,
            phone: step2?.phone ?? draftFields?.phone,
          }}
          onSubmit={handleStep2}
          onBack={() => setStep(0)}
        />
      )}

      {step === 2 && (
        <ResidenceStep
          defaultValues={step3Defaults}
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

      {resumedDraft && step === 0 && (
        <p
          className="mt-6 text-xs text-center text-brand-on-surface-variant"
          data-testid="signup-resumed"
        >
          We restored your previous progress. Choose your password again to continue.
        </p>
      )}

      <p className="mt-8 text-sm text-center text-brand-on-surface-variant">
        Already have an account?{" "}
        <Link
          href={ROUTES.AUTH.LOGIN}
          className="font-semibold underline-offset-2 hover:underline text-brand-navy"
        >
          Sign in
        </Link>
      </p>
    </AuthShell>
  );
}

// Re-export for tests.
export { loadLocalDraft };
