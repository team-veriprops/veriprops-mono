import { ROUTES } from "@/lib/routes";
import { NavItem } from "@/components/nav/MenuSidebar";

// Only routes with a built page appear here, so nothing in the sidebar 404s.
export const agentNavItems: NavItem[] = [
  { title: "Dashboard", href: ROUTES.AGENT.DASHBOARD, icon: "dashboard" },
  { title: "My Tasks", href: ROUTES.AGENT.TASKS, icon: "clipboardList" },
  { title: "Earnings", href: ROUTES.AGENT.EARNINGS, icon: "dollarSign" },
  { title: "Payouts", href: ROUTES.AGENT.PAYOUTS, icon: "creditCard" },
  { title: "Disputes", href: ROUTES.AGENT.DISPUTES, icon: "alertTriangle" },
  { title: "Profile", href: ROUTES.AGENT.PROFILE, icon: "user" },
];
