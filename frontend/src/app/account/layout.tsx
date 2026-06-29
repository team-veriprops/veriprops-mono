import AppShell from "@components/ui/AppShell";
import { accountNavItems } from "@components/account/nav";

export default function AccountLayout({ children }: { children: React.ReactNode }) {
  return <AppShell navItems={accountNavItems}>{children}</AppShell>;
}
