"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ArrowRight, ShieldCheck, UserPlus, LogIn, Briefcase } from "lucide-react";
import AuthShell from "./AuthShell";
import AuthHeading from "./AuthHeading";
import SocialAuthButtons, { AuthDivider } from "./SocialAuthButtons";
import { ROUTES, isAuthIntent, buildAuthUrl, AuthIntent } from "@lib/routes";

interface IntentCopy {
  eyebrow: string;
  title: string;
  subtitle: string;
  primaryCta: string;
  secondaryCta: string;
}

const COPY: Record<AuthIntent, IntentCopy> = {
  verify: {
    eyebrow: "Start a verification",
    title: "Verify a property — securely.",
    subtitle:
      "Create your account in under 2 minutes, then submit the property you want verified. Most reports return in 5–7 business days.",
    primaryCta: "Create my Veriprops account",
    secondaryCta: "I already have an account",
  },
  agent: {
    eyebrow: "Become an agent",
    title: "Join the verified agent network.",
    subtitle:
      "Apply once, get certified across roles you qualify for: Field, Surveyor, Registry, or Lawyer. Earn for every approved task.",
    primaryCta: "Apply to become an agent",
    secondaryCta: "I already have an account",
  },
  default: {
    eyebrow: "Welcome",
    title: "Continue to Veriprops.",
    subtitle:
      "Sign in to your account, or create a new one to start verifying property anywhere in Nigeria.",
    primaryCta: "Create an account",
    secondaryCta: "I already have an account",
  },
};

export default function AuthGateContainer() {
  const search = useSearchParams();
  const rawIntent = search.get("intent");
  const intent: AuthIntent = isAuthIntent(rawIntent) ? rawIntent : "default";
  const tier = search.get("tier");
  const redirect = search.get("redirect");

  const copy = COPY[intent];
  const signupHref = buildAuthUrl(ROUTES.AUTH.SIGNUP, { intent, tier, redirect });
  const loginHref = buildAuthUrl(ROUTES.AUTH.LOGIN, { intent, tier, redirect });

  return (
    <AuthShell
      panelHeading={
        intent === "agent" ? "Earn from verified work." : "Verify before you pay."
      }
      panelCopy={
        intent === "agent"
          ? "Veriprops connects you with paying customers who need exactly the work you do. Submit on your terms; get paid on time."
          : "Veriprops independently checks ownership, encumbrances, boundaries and physical reality of any Nigerian property — before you wire a single naira."
      }
    >
      <AuthHeading eyebrow={copy.eyebrow} title={copy.title} subtitle={copy.subtitle} />

      <div className="space-y-3">
        <Link
          href={signupHref}
          className="signature-gradient group flex items-center justify-between gap-3 px-5 py-4 rounded-xl text-white font-bold text-base transition-all duration-200 hover:opacity-95 active:scale-[0.99]"
          style={{ boxShadow: "0 8px 24px -6px rgba(0,13,34,0.3)" }}
        >
          <span className="inline-flex items-center gap-3">
            {intent === "agent" ? (
              <Briefcase className="w-5 h-5" strokeWidth={2.2} />
            ) : (
              <UserPlus className="w-5 h-5" strokeWidth={2.2} />
            )}
            {copy.primaryCta}
          </span>
          <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
        </Link>

        <Link
          href={loginHref}
          className="group flex items-center justify-between gap-3 px-5 py-4 rounded-xl text-base font-semibold transition-all duration-150 hover:bg-[var(--brand-surface-low)]"
          style={{
            border: "1px solid rgba(196,198,207,0.4)",
            color: "var(--brand-navy)",
            backgroundColor: "var(--brand-surface-card)",
          }}
        >
          <span className="inline-flex items-center gap-3">
            <LogIn className="w-5 h-5" strokeWidth={2.2} />
            {copy.secondaryCta}
          </span>
          <ArrowRight
            className="w-4 h-4 transition-transform group-hover:translate-x-0.5"
            style={{ color: "var(--brand-on-surface-variant)" }}
          />
        </Link>
      </div>

      <AuthDivider />

      <SocialAuthButtons verb="Continue with" intent={intent} />

      <div className="mt-10 flex items-start gap-3 p-4 rounded-xl" style={{ backgroundColor: "var(--brand-surface-low)" }}>
        <ShieldCheck className="w-5 h-5 shrink-0 mt-0.5" style={{ color: "var(--brand-viridian)" }} />
        <p className="text-xs leading-relaxed" style={{ color: "var(--brand-on-surface-variant)" }}>
          We never ask for your bank details, send payment links via DM, or use your data for anything beyond
          delivering verifications. Read our{" "}
          <Link href="/legal/privacy" className="font-semibold" style={{ color: "var(--brand-navy)" }}>
            Privacy Policy
          </Link>
          .
        </p>
      </div>
    </AuthShell>
  );
}
