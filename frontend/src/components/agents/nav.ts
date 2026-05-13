import { ROUTES } from "@/lib/routes";
import { NavItem } from "@/components/nav/MenuSidebar";

export const agentNavItems: NavItem[] = [
  { title: "Dashboard", href: ROUTES.AGENT.DASHBOARD, icon: "dashboard", has_separator_after: false },
  { title: "My Tasks", href: ROUTES.AGENT.DASHBOARD, icon: "clipboardList", has_separator_after: false },
  { title: "Profile", href: ROUTES.AGENT.PROFILE, icon: "user", has_separator_after: false },
  { title: "Coverage", href: ROUTES.AGENT.SETTINGS_COVERAGE, icon: "mapPin", has_separator_after: false },
  { title: "Availability", href: ROUTES.AGENT.SETTINGS_AVAILABILITY, icon: "activity", has_separator_after: false },
  { title: "Earnings", href: ROUTES.AGENT.EARNINGS, icon: "creditCard", has_separator_after: false },
  { title: "Payouts", href: ROUTES.AGENT.PAYOUTS, icon: "creditCard", has_separator_after: false },
  { title: "Onboarding", href: ROUTES.AGENT.ONBOARDING, icon: "userCog", has_separator_after: false },
  { title: "Notification Preferences", href: ROUTES.AGENT.NOTIFICATION_PREFERENCES, icon: "bell", has_separator_after: false },
];
