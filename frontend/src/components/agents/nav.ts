import { NavItem } from "@components/nav/PortalSidebar";
import { LayoutDashboard, ClipboardList, UserCog } from "lucide-react";

export const agentNavItems: NavItem[] = [
  { title: "Dashboard", href: "/agents/dashboard", icon: LayoutDashboard, has_separator_after: false },
  { title: "Onboarding", href: "/agents/onboarding", icon: ClipboardList, has_separator_after: true },
  { title: "Account", href: "/account", icon: UserCog, has_separator_after: false },
];
