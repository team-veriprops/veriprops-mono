import { ROUTES } from "@/lib/routes";
import { NavItem } from "@/components/nav/MenuSidebar";

export const adminNavItems: NavItem[] = [
  { title: "Dashboard", href: ROUTES.ADMIN.DASHBOARD, icon: "dashboard", has_separator_after: false },
  { title: "Verifications", href: ROUTES.ADMIN.VERIFICATIONS, icon: "fileCheck", has_separator_after: false },
  { title: "Agent Applications", href: ROUTES.ADMIN.AGENT_APPLICATIONS, icon: "userCog", has_separator_after: false },
  { title: "System Config", href: ROUTES.ADMIN.CONFIG, icon: "settings", has_separator_after: false },
];
