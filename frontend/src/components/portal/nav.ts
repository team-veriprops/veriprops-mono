import { ROUTES } from "@/lib/routes";
import { NavItem } from "@/components/nav/MenuSidebar";

export const portalNavItems: NavItem[] = [
  { title: "Dashboard", href: ROUTES.PORTAL.DASHBOARD, icon: "dashboard", has_separator_after: false },
  { title: "My Verifications", href: ROUTES.PORTAL.VERIFICATIONS, icon: "clipboardList", has_separator_after: false },
  { title: "Notifications", href: ROUTES.PORTAL.NOTIFICATIONS, icon: "bell", has_separator_after: false },
  { title: "Referrals", href: ROUTES.PORTAL.REFERRALS, icon: "gift", has_separator_after: false },
  { title: "Payment History", href: ROUTES.PORTAL.PAYMENTS, icon: "creditCard", has_separator_after: false },
  { title: "Notification Preferences", href: ROUTES.PORTAL.NOTIFICATION_PREFERENCES, icon: "settings", has_separator_after: false },
  { title: "Support", href: ROUTES.PORTAL.SUPPORT, icon: "helpCircle", has_separator_after: false },
];
