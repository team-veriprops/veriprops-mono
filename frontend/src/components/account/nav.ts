import { ROUTES } from "@/lib/routes";
import { NavItem } from "@/components/nav/MenuSidebar";

// Account-security surface (PRD §2.5–2.9). Icons are keys into AppShell's iconMap.
export const accountNavItems: NavItem[] = [
  { title: "Security Activity", href: ROUTES.ACCOUNT.SECURITY, icon: "activity" },
  { title: "Connected Devices", href: ROUTES.ACCOUNT.DEVICES, icon: "settings" },
  { title: "Linked Accounts", href: ROUTES.ACCOUNT.LINKED, icon: "users" },
  // PRD §26.4.4 — the WhatsApp number, which is an identity link rather than a sign-in one.
  { title: "WhatsApp", href: ROUTES.ACCOUNT.WHATSAPP, icon: "messageSquare" },
  { title: "Password", href: ROUTES.ACCOUNT.PASSWORD, icon: "userRoundKey" },
  // §19 / §N.5 — personal data management
  { title: "Consents", href: ROUTES.ACCOUNT.CONSENTS, icon: "fileText", section: "Privacy" },
  { title: "Data & Privacy", href: ROUTES.ACCOUNT.DATA_PRIVACY, icon: "user" },
];
