import { ROUTES } from "@/lib/routes";
import { NavItem } from "@/components/nav/MenuSidebar";

// Only routes with a built page appear here — items for later slices (e.g. Payment
// History) are restored as their slices land, so nothing in the sidebar 404s.
export const portalNavItems: NavItem[] = [
  { title: "Dashboard", href: ROUTES.PORTAL.DASHBOARD, icon: "dashboard", has_separator_after: false },
  { title: "My Verifications", href: ROUTES.PORTAL.VERIFICATIONS, icon: "clipboardList", has_separator_after: false },
  { title: "New Verification", href: ROUTES.PORTAL.VERIFICATIONS_NEW, icon: "fileCheck", has_separator_after: false },
  { title: "Messages", href: ROUTES.PORTAL.CHAT, icon: "messageSquare", has_separator_after: false },
  { title: "Support", href: ROUTES.PORTAL.SUPPORT, icon: "helpCircle", has_separator_after: false },
];
