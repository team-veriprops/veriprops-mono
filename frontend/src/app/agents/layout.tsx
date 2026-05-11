import AppShell from "@components/ui/AppShell";
import { agentNavItems } from "@components/agents/nav";
import SwRegistrar from "@components/agents/SwRegistrar";

export default function AgentsLayout({ children }: { children: React.ReactNode }) {
  return (
    <AppShell navItems={agentNavItems}>
      <SwRegistrar />
      {children}
    </AppShell>
  );
}
