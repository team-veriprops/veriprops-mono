import { ROUTES } from "@/lib/routes";
import { NavItem } from "@/components/nav/MenuSidebar";

export const agentNavItems: NavItem[] = [
  { title: "Dashboard", href: ROUTES.AGENT.DASHBOARD, icon: "dashboard", has_separator_after: false },
  { title: "My Tasks", href: ROUTES.AGENT.DASHBOARD, icon: "clipboardList", has_separator_after: false },
  { title: "Onboarding", href: ROUTES.AGENT.ONBOARDING, icon: "userCog", has_separator_after: false },
];
