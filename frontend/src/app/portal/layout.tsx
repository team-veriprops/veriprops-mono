import AppShell from "@components/ui/AppShell";
import { portalNavItems } from "@components/portal/nav";

export default function PortalLayout({ children }: { children: React.ReactNode }) {
  return <AppShell navItems={portalNavItems}>{children}</AppShell>;
}
