import { ROUTES } from "@/lib/routes";
import { NavItem } from "@/components/nav/MenuSidebar";

export const adminNavItems: NavItem[] = [
  { title: "Dashboard", href: ROUTES.ADMIN.DASHBOARD, icon: "dashboard", has_separator_after: false },
  { title: "Analytics", href: ROUTES.ADMIN.ANALYTICS, icon: "barChart", has_separator_after: true },
  { title: "Verifications", href: ROUTES.ADMIN.VERIFICATIONS, icon: "fileCheck", has_separator_after: false },
  { title: "Disputes", href: ROUTES.ADMIN.DISPUTES, icon: "alertTriangle", has_separator_after: false },
  { title: "Re-checks", href: ROUTES.ADMIN.RECHECKS, icon: "activity", has_separator_after: false },
  { title: "Message Review", href: ROUTES.ADMIN.HELD_MESSAGES, icon: "messageSquare", has_separator_after: false },
  { title: "Broadcasts", href: ROUTES.ADMIN.BROADCASTS, icon: "megaphone", has_separator_after: true },
  { title: "Agent Applications", href: ROUTES.ADMIN.AGENT_APPLICATIONS, icon: "userRoundKey", has_separator_after: false },
  { title: "Admin Team", href: ROUTES.ADMIN.TEAM, icon: "users", has_separator_after: true },
  { title: "Finance", href: ROUTES.ADMIN.FINANCE, icon: "dollarSign", has_separator_after: false },
  { title: "Payouts", href: ROUTES.ADMIN.FINANCE_PAYOUTS, icon: "creditCard", has_separator_after: false },
  { title: "Commission Rules", href: ROUTES.ADMIN.COMMISSION_RULES, icon: "dollarSign", has_separator_after: false },
  { title: "Pricing", href: ROUTES.ADMIN.PRICING, icon: "tag", has_separator_after: true },
  { title: "Trust Score Weights", href: ROUTES.ADMIN.TRUST_SCORE_WEIGHTS, icon: "settings", has_separator_after: false },
  { title: "System Config", href: ROUTES.ADMIN.SYSTEM_CONFIG, icon: "settings", has_separator_after: true },
  // §19 audit & compliance maturity
  { title: "Audit Log", href: ROUTES.ADMIN.AUDIT_ACTIONS, icon: "clipboardList", has_separator_after: false },
  { title: "Erasure Requests", href: ROUTES.ADMIN.ERASURE_REQUESTS, icon: "alertTriangle", has_separator_after: false },
];
