import { NavItem } from "@components/nav/PortalSidebar";
import {
  LayoutDashboard,
  FileCheck,
  ClipboardList,
  AlertTriangle,
  MessageSquare,
  CreditCard,
  Settings,
  HelpCircle,
} from "lucide-react";


export const portalNavItems: NavItem[] = [
  { title: "Dashboard", href: "/portal/dashboard", icon: LayoutDashboard, has_separator_after: false },
  { title: "My Verifications", href: "/portal/verifications", icon: FileCheck, has_separator_after: false },
  { title: "Payments", href: "/portal/payments", icon: CreditCard, has_separator_after: false },
  { title: "Chats", href: "/portal/chats", icon: MessageSquare, has_separator_after: false },
  { title: "Disputes", href: "/portal/disputes", icon: AlertTriangle, has_separator_after: false },
  { title: "Tasks", href: "/portal/tasks", icon: ClipboardList, has_separator_after: true },
  { title: "Settings", href: "/portal/settings", icon: Settings, has_separator_after: false },
  { title: "Support & Help", href: "/portal/support", icon: HelpCircle, has_separator_after: false },
];
