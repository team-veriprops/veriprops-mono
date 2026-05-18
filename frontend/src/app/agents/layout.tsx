import AppShell from "@components/ui/AppShell";
import { agentNavItems } from "@components/agents/nav";
import SwRegistrar from "@components/agents/SwRegistrar";
import OnboardingGateModal from "@components/agents/onboarding/OnboardingGateModal";

export default function AgentsLayout({ children }: { children: React.ReactNode }) {
  return (
    <AppShell navItems={agentNavItems}>
      <SwRegistrar />
      <OnboardingGateModal />
      {children}
    </AppShell>
  );
}
