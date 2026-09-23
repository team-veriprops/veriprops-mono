import { ROUTES } from "@/lib/routes";
import { NavItem } from "@/components/nav/MenuSidebar";

// Only routes with a built page appear here — items for later slices (e.g. Payment
// History) are restored as their slices land, so nothing in the sidebar 404s.
// `section` on an item opens a labeled sidebar group; following items inherit it.
export const portalNavItems: NavItem[] = [
  { title: "Dashboard", href: ROUTES.PORTAL.DASHBOARD, icon: "dashboard", section: "Overview" },
  { title: "My Verifications", href: ROUTES.PORTAL.VERIFICATIONS, icon: "clipboardList", section: "Verifications" },
  // { title: "New Verification", href: ROUTES.PORTAL.VERIFICATIONS_NEW, icon: "fileCheck" },
  { title: "Messages", href: ROUTES.PORTAL.CHAT, icon: "messageSquare" },
  // { title: "Refer & earn", href: ROUTES.PORTAL.REFERRALS, icon: "gift" },
  { title: "Support", href: ROUTES.PORTAL.SUPPORT, icon: "helpCircle", section: "Help" },
  // Applying is what grants the agent persona (PRD §3.2, additive — the customer keeps their own
  // portal). Until this existed there was no way in from inside the portal at all: the marketing
  // call to action points at a guest-only gate, which turns a signed-in customer away.
  {
    title: "Become an Agent",
    href: ROUTES.AGENT.APPLY,
    icon: "userCog",
    hiddenForAgents: true,
  },
];
