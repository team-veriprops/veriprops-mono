"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@3rdparty/ui/button";
import { CheckCircle2, ShieldCheck, AlertCircle, LogIn } from "lucide-react";
import { ROUTES } from "@lib/routes";
import { useAcceptInvitationMutation } from "@components/admin/libs/useAdminQueries";
import type { AcceptInviteResult } from "@components/admin/libs/admin-service";
import { getErrorMessage } from "@lib/utils";

export default function AdminInviteAcceptPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [result, setResult] = useState<AcceptInviteResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const accept = useAcceptInvitationMutation();

  useEffect(() => {
    let cancelled = false;
    params.then(async (p) => {
      if (cancelled) return;
      setToken(p.token);
      try {
        const res = await accept.mutateAsync(p.token);
        if (!cancelled) setResult(res.data ?? null);
      } catch (e) {
        if (!cancelled) setError(getErrorMessage(e as Error));
      }
    });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params]);

  if (error) {
    return (
      <Card
        accent="var(--destructive)"
        accentBg="rgba(186,26,26,0.06)"
        icon={<AlertCircle className="w-7 h-7" />}
        title="Invitation not valid"
        body={error}
      />
    );
  }

  if (!result) {
    return (
      <div
        className="min-h-screen flex items-center justify-center text-sm"
        style={{ color: "var(--brand-on-surface-variant)" }}
      >
        Verifying invitation…
      </div>
    );
  }

  if (result.branch === "ACCEPTED") {
    return (
      <Card
        accent="var(--success)"
        accentBg="rgba(58,154,106,0.08)"
        icon={<CheckCircle2 className="w-7 h-7" />}
        title="You're now an admin"
        body={`Your account ${result.email} has been promoted to ${result.subRole}.`}
        cta={{ label: "Go to admin dashboard", onClick: () => router.push(ROUTES.ADMIN.DASHBOARD) }}
      />
    );
  }

  if (result.branch === "ALREADY_ADMIN") {
    return (
      <Card
        accent="var(--brand-viridian)"
        accentBg="var(--brand-viridian-xlight)"
        icon={<ShieldCheck className="w-7 h-7" />}
        title="You're already an admin"
        body={`The invitation has been retired — you can sign in to ${result.email} as usual.`}
        cta={{ label: "Continue to login", onClick: () => router.push(ROUTES.AUTH.LOGIN) }}
      />
    );
  }

  if (result.branch === "LOGIN_REQUIRED") {
    return (
      <Card
        accent="var(--brand-navy)"
        accentBg="var(--brand-surface-low)"
        icon={<LogIn className="w-7 h-7" />}
        title="Sign in to accept"
        body={`We found an existing account for ${result.email}. Sign in there, then re-open this link to attach admin access.`}
        cta={{
          label: "Go to login",
          onClick: () =>
            router.push(`${ROUTES.AUTH.LOGIN}?redirect=/auth/admin-invite/${token}`),
        }}
      />
    );
  }

  // SIGNUP_REQUIRED
  return (
    <Card
      accent="var(--brand-viridian)"
      accentBg="var(--brand-viridian-xlight)"
      icon={<ShieldCheck className="w-7 h-7" />}
      title="Create your admin account"
      body={`We need to set up an account for ${result.email} before granting ${result.subRole} access.`}
      cta={{
        label: "Continue to signup",
        onClick: () =>
          router.push(
            `${ROUTES.AUTH.SIGNUP}?email=${encodeURIComponent(result.email)}&adminInvite=${token}`,
          ),
      }}
    />
  );
}

function Card({
  accent,
  accentBg,
  icon,
  title,
  body,
  cta,
}: {
  accent: string;
  accentBg: string;
  icon: React.ReactNode;
  title: string;
  body: string;
  cta?: { label: string; onClick: () => void };
}) {
  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div
        className="rounded-2xl p-8 text-center max-w-md w-full space-y-5"
        style={{
          backgroundColor: "var(--brand-surface-card)",
          boxShadow: "0px 24px 48px rgba(0,13,34,0.06)",
        }}
      >
        <div
          className="mx-auto w-14 h-14 rounded-full flex items-center justify-center"
          style={{ backgroundColor: accentBg, color: accent }}
        >
          {icon}
        </div>
        <div>
          <h1
            className="text-2xl font-semibold tracking-tight"
            style={{ color: "var(--brand-navy)", fontFamily: "var(--font-display, Manrope)" }}
          >
            {title}
          </h1>
          <p
            className="text-sm mt-2 leading-6"
            style={{ color: "var(--brand-on-surface-variant)" }}
          >
            {body}
          </p>
        </div>
        {cta && (
          <Button type="button" onClick={cta.onClick}>
            {cta.label}
          </Button>
        )}
      </div>
    </div>
  );
}
