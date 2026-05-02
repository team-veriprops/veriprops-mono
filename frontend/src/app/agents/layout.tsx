import AppShell from "@components/ui/AppShell";
import { agentNavItems } from "@components/agents/nav";

export default function AgentsLayout({ children }: { children: React.ReactNode }) {
  return <AppShell navItems={agentNavItems}>{children}</AppShell>;
}
