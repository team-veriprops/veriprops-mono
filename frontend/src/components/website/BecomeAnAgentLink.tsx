"use client";

import Link from "next/link";
import { ReactNode } from "react";

import { useAuthStore } from "@components/website/auth/libs/useAuthStore";
import { AuthIntent, UserPersona } from "@components/website/auth/models";
import { ROUTES, buildAuthUrl } from "@lib/routes";

/**
 * Where "become an agent" should send this particular reader.
 *
 * The marketing pages used to point everyone at the signed-out auth gate, which is guest-only — so
 * a customer already signed in was bounced back to their dashboard and had no way to apply at all.
 * Applying is what grants the AGENT persona (PRD §3.2, additive), so an existing customer goes
 * straight to the application; someone who already holds the persona goes to their agent area.
 */
export function useBecomeAnAgentHref(): string {
  const session = useAuthStore((s) => s.session);

  if (!session) return buildAuthUrl(ROUTES.AUTH.GATE, { intent: AuthIntent.AGENT });
  return session.user?.personas?.includes(UserPersona.AGENT)
    ? ROUTES.AGENT.DASHBOARD
    : ROUTES.AGENT.APPLY;
}

/**
 * The call to action itself. A client boundary around one link, so the marketing sections that
 * host it stay server components.
 */
export default function BecomeAnAgentLink({
  className,
  children,
  "data-testid": testId,
}: {
  className?: string;
  children: ReactNode;
  "data-testid"?: string;
}) {
  return (
    <Link href={useBecomeAnAgentHref()} className={className} data-testid={testId}>
      {children}
    </Link>
  );
}
