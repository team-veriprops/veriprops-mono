import { ROUTES } from "@/lib/routes";
import { NavItem } from "@/components/nav/MenuSidebar";

// Only routes with a built page appear here — Earnings and Payouts (S19) are restored
// as their slice lands, so nothing in the sidebar 404s.
export const agentNavItems: NavItem[] = [
  { title: "Dashboard", href: ROUTES.AGENT.DASHBOARD, icon: "dashboard", has_separator_after: false },
  { title: "My Tasks", href: ROUTES.AGENT.TASKS, icon: "clipboardList", has_separator_after: false },
  { title: "Disputes", href: ROUTES.AGENT.DISPUTES, icon: "alertTriangle", has_separator_after: false },
];
