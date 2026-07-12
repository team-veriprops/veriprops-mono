import { ROUTES } from "@/lib/routes";
import { NavItem } from "@/components/nav/MenuSidebar";

// Only routes with a built page appear here — items for later slices (e.g. Payment
// History) are restored as their slices land, so nothing in the sidebar 404s.
export const portalNavItems: NavItem[] = [
  { title: "Dashboard", href: ROUTES.PORTAL.DASHBOARD, icon: "dashboard" },
  { title: "My Verifications", href: ROUTES.PORTAL.VERIFICATIONS, icon: "clipboardList" },
  { title: "New Verification", href: ROUTES.PORTAL.VERIFICATIONS_NEW, icon: "fileCheck" },
  { title: "Messages", href: ROUTES.PORTAL.CHAT, icon: "messageSquare" },
  { title: "Refer & earn", href: ROUTES.PORTAL.REFERRALS, icon: "gift" },
  { title: "Support", href: ROUTES.PORTAL.SUPPORT, icon: "helpCircle" },
];
