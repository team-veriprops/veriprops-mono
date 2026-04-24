import { NavItem } from "@components/nav/PortalSidebar";
import {
  LayoutDashboard,
  UserCog,
  ClipboardList,
  AlertTriangle,
  MessageSquare,
  UserRoundKey,
  Settings,
  HelpCircle,
} from "lucide-react";


export const adminNavItems: NavItem[] = [
  { title: "Dashboard", href: "/admin/dashboard", icon: LayoutDashboard, has_separator_after: false },
  { title: "User Management", href: "/admin/users", icon: UserCog , has_separator_after: false },
  { title: "Role Management", href: "/admin/roles", icon: UserRoundKey, has_separator_after: false },
  { title: "Chats", href: "/admin/chats", icon: MessageSquare, has_separator_after: false },
  { title: "Disputes", href: "/admin/disputes", icon: AlertTriangle, has_separator_after: false },
  { title: "Tasks", href: "/admin/tasks", icon: ClipboardList, has_separator_after: true },
  { title: "Settings", href: "/admin/settings", icon: Settings, has_separator_after: false },
  { title: "Support & Help", href: "/admin/support", icon: HelpCircle, has_separator_after: false },
];
