"use client";

import { usePathname } from "next/navigation";

import AppShell from "@components/ui/AppShell";
import { agentNavItems } from "@components/agents/nav";
import AgentOnboardingContainer from "@components/agents/onboarding/AgentOnboardingContainer";
import { useAgentStatusQuery } from "@components/agents/libs/useAgentQueries";
import { ROUTES } from "@lib/routes";
import { AgentApplicationStatus } from "@/types/agent";

/**
 * Compulsory onboarding gate (PRD §3.1): an agent with no application yet, or a REJECTED one, is
 * forced into the non-closable onboarding wizard on every `/agents/*` route. PENDING/APPROVED
 * agents see their normal area untouched.
 *
 * `/agents/apply` is the one exception, and it is a distinction rather than a special case: since
 * the route guard admits a customer there (§3.2 — applying is what grants the agent persona, so
 * gating the application behind it made the application unreachable), the gate covers *the agent
 * area* while the application route renders its own wizard. That one is closable for anyone with a
 * portal to return to, so someone who followed "Become an Agent" and changed their mind is not
 * trapped behind a layer that covers the nav.
 */
export default function AgentsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { data: status, isLoading } = useAgentStatusQuery();
  const needsOnboarding = !isLoading && (!status || status.status === AgentApplicationStatus.REJECTED);
  const isApplicationRoute = pathname === ROUTES.AGENT.APPLY;

  return (
    <AppShell navItems={agentNavItems}>
      {needsOnboarding && !isApplicationRoute ? (
        <AgentOnboardingContainer closable={false} />
      ) : (
        children
      )}
    </AppShell>
  );
}
