import { ROUTES } from "@/lib/routes";
import { NavItem } from "@/components/nav/MenuSidebar";

export const adminNavItems: NavItem[] = [
  { title: "Dashboard", href: ROUTES.ADMIN.DASHBOARD, icon: "dashboard", has_separator_after: false },
  { title: "Verifications", href: ROUTES.ADMIN.VERIFICATIONS, icon: "fileCheck", has_separator_after: false },
  { title: "Agent Applications", href: ROUTES.ADMIN.AGENT_APPLICATIONS, icon: "userCog", has_separator_after: false },
  { title: "Disputes", href: ROUTES.ADMIN.DISPUTES, icon: "alertTriangle", has_separator_after: false },
  { title: "Re-check Requests", href: ROUTES.ADMIN.RECHECKS, icon: "fileCheck", has_separator_after: false },
  { title: "Payouts", href: ROUTES.ADMIN.PAYOUTS, icon: "creditCard", has_separator_after: false },
  { title: "Commission Rules", href: ROUTES.ADMIN.COMMISSION_RULES, icon: "fileCheck", has_separator_after: false },
  { title: "Fraud Review", href: ROUTES.ADMIN.FRAUD_FLAGS, icon: "alertTriangle", has_separator_after: false },
  { title: "System Config", href: ROUTES.ADMIN.CONFIG, icon: "settings", has_separator_after: false },
];
