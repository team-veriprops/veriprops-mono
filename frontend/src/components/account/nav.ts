import { ROUTES } from "@/lib/routes";
import { NavItem } from "@/components/nav/MenuSidebar";

// Account-security surface (PRD §2.5–2.9). Icons are keys into AppShell's iconMap.
export const accountNavItems: NavItem[] = [
  { title: "Security Activity", href: ROUTES.ACCOUNT.SECURITY, icon: "activity", has_separator_after: false },
  { title: "Connected Devices", href: ROUTES.ACCOUNT.DEVICES, icon: "settings", has_separator_after: false },
  { title: "Linked Accounts", href: ROUTES.ACCOUNT.LINKED, icon: "users", has_separator_after: false },
  { title: "Password", href: ROUTES.ACCOUNT.PASSWORD, icon: "userRoundKey", has_separator_after: false },
];
