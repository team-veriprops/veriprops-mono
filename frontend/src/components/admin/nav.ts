import { ROUTES } from "@/lib/routes";
import { NavItem } from "@/components/nav/MenuSidebar";

// Only routes with a built page appear here — the remaining items (Analytics, Commission
// Rules, Pricing, Finance, Broadcasts, Audit Log, Erasure) are restored as their slices land,
// so nothing in the sidebar 404s.
export const adminNavItems: NavItem[] = [
  { title: "Dashboard", href: ROUTES.ADMIN.DASHBOARD, icon: "dashboard", has_separator_after: false },
  { title: "Verifications", href: ROUTES.ADMIN.VERIFICATIONS, icon: "fileCheck", has_separator_after: false },
  { title: "Disputes", href: ROUTES.ADMIN.DISPUTES, icon: "alertTriangle", has_separator_after: false },
  { title: "Re-checks", href: ROUTES.ADMIN.RECHECKS, icon: "activity", has_separator_after: false },
  { title: "Message Review", href: ROUTES.ADMIN.HELD_MESSAGES, icon: "messageSquare", has_separator_after: false },
  { title: "Agent Applications", href: ROUTES.ADMIN.AGENT_APPLICATIONS, icon: "userRoundKey", has_separator_after: false },
  { title: "Admin Team", href: ROUTES.ADMIN.TEAM, icon: "users", has_separator_after: false },
  { title: "Payouts", href: ROUTES.ADMIN.FINANCE_PAYOUTS, icon: "creditCard", has_separator_after: false },
  { title: "Commission Rules", href: ROUTES.ADMIN.COMMISSION_RULES, icon: "dollarSign", has_separator_after: false },
  { title: "Trust Score Weights", href: ROUTES.ADMIN.TRUST_SCORE_WEIGHTS, icon: "settings", has_separator_after: false },
  { title: "System Config", href: ROUTES.ADMIN.SYSTEM_CONFIG, icon: "settings", has_separator_after: false },
];
