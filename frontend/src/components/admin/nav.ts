import { ROUTES } from "@/lib/routes";
import { NavItem } from "@/components/nav/MenuSidebar";

export const adminNavItems: NavItem[] = [
  { title: "Dashboard", href: ROUTES.ADMIN.DASHBOARD, icon: "dashboard", has_separator_after: false },
  { title: "Analytics", href: ROUTES.ADMIN.ANALYTICS, icon: "barChart", has_separator_after: false },
  { title: "Verifications", href: ROUTES.ADMIN.VERIFICATIONS, icon: "fileCheck", has_separator_after: false },
  { title: "Disputes", href: ROUTES.ADMIN.DISPUTES, icon: "alertTriangle", has_separator_after: false },
  { title: "Re-check Requests", href: ROUTES.ADMIN.RECHECKS, icon: "fileCheck", has_separator_after: false },
  { title: "Commission Rules", href: ROUTES.ADMIN.COMMISSION_RULES, icon: "fileCheck", has_separator_after: false },
  { title: "Pricing", href: ROUTES.ADMIN.PRICING, icon: "tag", has_separator_after: false },
  { title: "Finance", href: ROUTES.ADMIN.FINANCE, icon: "dollarSign", has_separator_after: false },
  { title: "Broadcasts", href: ROUTES.ADMIN.BROADCASTS, icon: "megaphone", has_separator_after: false },
  { title: "Audit Log", href: ROUTES.ADMIN.AUDIT_ACTIONS, icon: "fileText", has_separator_after: false },
  { title: "Erasure Requests", href: ROUTES.ADMIN.ERASURE_REQUESTS, icon: "userRoundKey", has_separator_after: false },
  { title: "System Config", href: ROUTES.ADMIN.CONFIG, icon: "settings", has_separator_after: false },
];
