import AppShell from "@components/ui/AppShell";
import { adminNavItems } from "@components/admin/nav";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return <AppShell navItems={adminNavItems}>{children}</AppShell>;
}
