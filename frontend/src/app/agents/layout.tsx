"use client";

import AppShell from "@components/ui/AppShell";
import { agentNavItems } from "@components/agents/nav";
import AgentOnboardingContainer from "@components/agents/onboarding/AgentOnboardingContainer";
import { useAgentStatusQuery } from "@components/agents/libs/useAgentQueries";
import { AgentApplicationStatus } from "@/types/agent";

/**
 * Compulsory onboarding gate (PRD §3.1): an agent with no application yet, or a
 * REJECTED one, is forced into the non-closable onboarding wizard on every
 * `/agents/*` route — including `/agents/apply` itself, so there's no route-based
 * special-casing. PENDING/APPROVED agents see their normal area untouched.
 */
export default function AgentsLayout({ children }: { children: React.ReactNode }) {
  const { data: status, isLoading } = useAgentStatusQuery();
  const needsOnboarding = !isLoading && (!status || status.status === AgentApplicationStatus.REJECTED);

  return (
    <AppShell navItems={agentNavItems}>
      {needsOnboarding ? <AgentOnboardingContainer closable={false} /> : children}
    </AppShell>
  );
}
