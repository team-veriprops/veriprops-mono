import { ROUTES } from "@/lib/routes";
import { NavItem } from "@/components/nav/MenuSidebar";

// Only routes with a built page appear here — the S15+ items (Analytics, Disputes,
// Re-checks, Commission Rules, Pricing, Finance, Broadcasts, Audit Log, Erasure, System
// Config) are restored as their slices land, so nothing in the sidebar 404s.
export const adminNavItems: NavItem[] = [
  { title: "Dashboard", href: ROUTES.ADMIN.DASHBOARD, icon: "dashboard", has_separator_after: false },
  { title: "Verifications", href: ROUTES.ADMIN.VERIFICATIONS, icon: "fileCheck", has_separator_after: false },
  { title: "Agent Applications", href: ROUTES.ADMIN.AGENT_APPLICATIONS, icon: "userRoundKey", has_separator_after: false },
  { title: "Admin Team", href: ROUTES.ADMIN.TEAM, icon: "users", has_separator_after: false },
  { title: "Trust Score Weights", href: ROUTES.ADMIN.TRUST_SCORE_WEIGHTS, icon: "settings", has_separator_after: false },
];
