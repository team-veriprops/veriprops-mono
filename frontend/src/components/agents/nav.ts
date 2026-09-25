import { ROUTES } from "@/lib/routes";
import { NavItem } from "@/components/nav/MenuSidebar";

// Only routes with a built page appear here, so nothing in the sidebar 404s.
// `section` on an item opens a labeled sidebar group; following items inherit it.
export const agentNavItems: NavItem[] = [
  { title: "Dashboard", href: ROUTES.AGENT.DASHBOARD, icon: "dashboard", section: "Overview" },
  { title: "My Tasks", href: ROUTES.AGENT.TASKS, icon: "clipboardList", section: "Work" },
  { title: "Disputes", href: ROUTES.AGENT.DISPUTES, icon: "alertTriangle" },
  { title: "Earnings", href: ROUTES.AGENT.EARNINGS, icon: "dollarSign", section: "Finance" },
  { title: "Payouts", href: ROUTES.AGENT.PAYOUTS, icon: "creditCard" },
  { title: "Profile", href: ROUTES.AGENT.PROFILE, icon: "user", section: "Account" },
  // The mirror of the portal's "Become an Agent" (PRD §3.2, additive). An agent-path signup holds
  // no customer persona, so without this there is no way for them to have a property verified —
  // the marketing call to action is guest-only and /portal/* is shut to them.
  {
    title: "Verify a Property",
    href: ROUTES.AGENT.VERIFY_PROPERTY,
    icon: "fileCheck",
    hiddenForCustomers: true,
  },
];
