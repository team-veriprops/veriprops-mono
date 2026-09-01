import { ROUTES } from "@/lib/routes";
import { NavItem } from "@/components/nav/MenuSidebar";

// `section` on an item opens a labeled sidebar group; following items inherit it.
export const adminNavItems: NavItem[] = [
  { title: "Dashboard", href: ROUTES.ADMIN.DASHBOARD, icon: "dashboard", section: "Overview" },
  { title: "Analytics", href: ROUTES.ADMIN.ANALYTICS, icon: "barChart" },
  { title: "Verifications", href: ROUTES.ADMIN.VERIFICATIONS, icon: "fileCheck", section: "Operations" },
  { title: "Disputes", href: ROUTES.ADMIN.DISPUTES, icon: "alertTriangle" },
  { title: "Re-checks", href: ROUTES.ADMIN.RECHECKS, icon: "activity" },
  { title: "Message Review", href: ROUTES.ADMIN.HELD_MESSAGES, icon: "messageSquare" },
  { title: "Broadcasts", href: ROUTES.ADMIN.BROADCASTS, icon: "megaphone" },
  { title: "Users", href: ROUTES.ADMIN.USERS, icon: "users", section: "People" },
  { title: "Agent Applications", href: ROUTES.ADMIN.AGENT_APPLICATIONS, icon: "userRoundKey" },
  { title: "Admin Team", href: ROUTES.ADMIN.TEAM, icon: "users" },
  { title: "Finance", href: ROUTES.ADMIN.FINANCE, icon: "dollarSign", section: "Finance" },
  { title: "Payouts", href: ROUTES.ADMIN.FINANCE_PAYOUTS, icon: "creditCard" },
  { title: "Commission Rules", href: ROUTES.ADMIN.COMMISSION_RULES, icon: "dollarSign" },
  { title: "Pricing", href: ROUTES.ADMIN.PRICING, icon: "tag" },
  { title: "Trust Score Weights", href: ROUTES.ADMIN.TRUST_SCORE_WEIGHTS, icon: "settings", section: "Settings" },
  { title: "System Config", href: ROUTES.ADMIN.SYSTEM_CONFIG, icon: "settings" },
  // §7.7 launch gate — which templates Meta has approved.
  { title: "WhatsApp Templates", href: ROUTES.ADMIN.WHATSAPP_TEMPLATES, icon: "messageSquare" },
  // §19 audit & compliance maturity
  { title: "Audit Log", href: ROUTES.ADMIN.AUDIT_ACTIONS, icon: "clipboardList", section: "Compliance" },
  { title: "Erasure Requests", href: ROUTES.ADMIN.ERASURE_REQUESTS, icon: "alertTriangle" },
];
