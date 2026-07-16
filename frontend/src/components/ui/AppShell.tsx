"use client";

import { useCallback, useState, useSyncExternalStore } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Activity,
  Bell,
  BarChart2,
  DollarSign,
  FileText,
  LayoutDashboard,
  Megaphone,
  Tag,
  UserCog,
  ClipboardList,
  AlertTriangle,
  MessageSquare,
  UserRoundKey,
  Settings,
  HelpCircle,
  FileCheck,
  CreditCard,
  User,
  Users,
  MapPin,
  Gift,
  ChevronsLeft,
  ChevronsRight,
  LogOut,
  Menu,
  X,
} from "lucide-react";
import NotificationBell from "@components/shared/notifications/NotificationBell";
import ChatButton from "@components/chat/ChatButton";
import PortalSwitcher from "@components/ui/PortalSwitcher";
import { useLogoutMutation } from "@components/website/auth/libs/useAuthQueries";
import { useAuthStore } from "@components/website/auth/libs/useAuthStore";
import { UserType, UserPersona, type AuthUser } from "@components/website/auth/models";
import { groupNavItems, NavItem } from "@/components/nav/MenuSidebar";
import { ROUTES } from "@lib/routes";
import TopNavBreadcrumb from "@components/ui/TopNav/TopNavBreadcrumb";
import TopNavUserMenu from "@components/ui/TopNav/TopNavUserMenu";
import ToolTipComponent from "@components/ui/ToolTipComponent";
import BrandLogo from "./BrandLogo";

interface AppShellProps {
  navItems: NavItem[];
  children: React.ReactNode;
}

const SIDEBAR_COLLAPSED_STORAGE_KEY = "veriprops.sidebar-collapsed";

// localStorage-backed collapse preference, read via useSyncExternalStore so the
// server render (always expanded) hydrates safely before the stored value applies.
const collapseListeners = new Set<() => void>();
const subscribeToCollapse = (onChange: () => void) => {
  collapseListeners.add(onChange);
  return () => collapseListeners.delete(onChange);
};
const readCollapsed = () => localStorage.getItem(SIDEBAR_COLLAPSED_STORAGE_KEY) === "true";

function useSidebarCollapsed(): [boolean, () => void] {
  const collapsed = useSyncExternalStore(subscribeToCollapse, readCollapsed, () => false);
  const toggle = useCallback(() => {
    localStorage.setItem(SIDEBAR_COLLAPSED_STORAGE_KEY, String(!readCollapsed()));
    collapseListeners.forEach((notify) => notify());
  }, []);
  return [collapsed, toggle];
}

const iconMap = {
  dashboard: LayoutDashboard,
  userCog: UserCog,
  clipboardList: ClipboardList,
  alertTriangle: AlertTriangle,
  messageSquare: MessageSquare,
  userRoundKey: UserRoundKey,
  settings: Settings,
  helpCircle: HelpCircle,
  fileCheck: FileCheck,
  creditCard: CreditCard,
  user: User,
  users: Users,
  mapPin: MapPin,
  activity: Activity,
  gift: Gift,
  bell: Bell,
  barChart: BarChart2,
  tag: Tag,
  dollarSign: DollarSign,
  fileText: FileText,
  megaphone: Megaphone,
} as const;

interface SidebarNavProps {
  navItems: NavItem[];
  pathname: string;
  onNavItemClick: () => void;
  showUserSection: boolean;
  user: AuthUser | null | undefined;
  initials: string;
  onLogout: () => void;
  isLoggingOut: boolean;
  /** Icon-rail mode (desktop collapse). The mobile drawer never collapses. */
  collapsed?: boolean;
  /** Renders a close button in the brand header (mobile drawer only). */
  onClose?: () => void;
}

function SidebarNav({
  navItems,
  pathname,
  onNavItemClick,
  showUserSection,
  user,
  initials,
  onLogout,
  isLoggingOut,
  collapsed = false,
  onClose,
}: SidebarNavProps) {
  const sections = groupNavItems(navItems);

  return (
    <div className="flex flex-col h-full">
      {/* Brand header zone — matches the top nav height so the borders align */}
      <div
        className={`flex items-center h-14 shrink-0 border-b border-sidebar-border ${
          collapsed ? "justify-center px-2" : "justify-between px-4"
        }`}
      >
        <BrandLogo variant="light" size={collapsed ? "compact" : "default"} />
        {onClose && (
          <button
            onClick={onClose}
            aria-label="Close menu"
            className="p-1.5 rounded-lg text-sidebar-foreground hover:text-sidebar-foreground-active hover:bg-white/5 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        )}
      </div>

      {/* Nav items */}
      <nav className={`flex-1 py-4 overflow-y-auto overflow-x-hidden ${collapsed ? "px-2" : "px-3"}`}>
        {sections.map((section, sectionIndex) => (
          <div key={section.label ?? sectionIndex}>
            {sectionIndex > 0 && collapsed && (
              <div className="my-2 mx-2 border-t border-sidebar-border" />
            )}
            {section.label && !collapsed && (
              <div
                className={`px-3 pb-1.5 ${
                  sectionIndex > 0 ? "pt-5" : "pt-1"
                } text-[11px] font-semibold uppercase tracking-wider text-sidebar-muted`}
              >
                {section.label}
              </div>
            )}
            <div className="space-y-0.5">
              {section.items.map((item) => {
                const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`);
                const Icon = iconMap[item.icon];

                if (!Icon) return null;

                const link = (
                  <Link
                    href={item.href}
                    onClick={onNavItemClick}
                    aria-current={isActive ? "page" : undefined}
                    aria-label={collapsed ? item.title : undefined}
                    className={`flex items-center gap-3 rounded-lg border text-sm font-medium transition-colors duration-150 ${
                      collapsed ? "justify-center py-2.5" : "px-3 py-2.5"
                    } ${
                      isActive
                        ? "bg-sidebar-accent text-sidebar-accent-foreground border-sidebar-accent"
                        : "text-sidebar-foreground border-transparent hover:text-sidebar-foreground-active hover:bg-white/5"
                    }`}
                  >
                    <Icon className="w-4 h-4 shrink-0" strokeWidth={isActive ? 2.5 : 1.75} />
                    {!collapsed && item.title}
                  </Link>
                );

                return collapsed ? (
                  <ToolTipComponent key={item.href} label={item.title} side="right">
                    {link}
                  </ToolTipComponent>
                ) : (
                  <div key={item.href}>{link}</div>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* User + logout — mobile drawer only */}
      {showUserSection && (
        <div className="px-4 py-4 border-t border-sidebar-border">
          <div className="flex items-center gap-3 mb-3 px-1">
            <Link
              href={ROUTES.ACCOUNT.SECURITY}
              onClick={onNavItemClick}
              className="flex items-center gap-3 flex-1 min-w-0 group"
            >
              <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-xs font-bold bg-sidebar-accent text-sidebar-accent-foreground transition-opacity group-hover:opacity-80">
                {initials}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-semibold truncate group-hover:underline text-sidebar-foreground-active">
                  {user ? `${user.firstName} ${user.lastName}` : "Loading..."}
                </div>
                <div className="text-xs truncate text-sidebar-muted">{user?.email ?? ""}</div>
              </div>
            </Link>
            <div className="shrink-0">
              <NotificationBell dark />
            </div>
          </div>
          <button
            onClick={onLogout}
            disabled={isLoggingOut}
            className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium text-sidebar-foreground hover:text-sidebar-foreground-active hover:bg-white/5 transition-colors duration-150"
          >
            <LogOut className="w-4 h-4" strokeWidth={1.75} />
            {isLoggingOut ? "Signing out…" : "Sign out"}
          </button>
        </div>
      )}
    </div>
  );
}

export default function AppShell({ navItems, children }: AppShellProps) {
  const pathname = usePathname();
  const router = useRouter();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [collapsed, toggleCollapsed] = useSidebarCollapsed();

  const session = useAuthStore((s) => s.session);
  const user = session?.user;
  const initials = user
    ? `${user.firstName?.[0] ?? ""}${user.lastName?.[0] ?? ""}`.toUpperCase() || "U"
    : "U";

  const logout = useLogoutMutation();
  const handleLogout = () => {
    logout.mutate(undefined, {
      onSuccess: () => router.push(ROUTES.AUTH.LOGIN),
    });
  };

  const notificationPrefsHref =
    user?.userType === UserType.ADMIN
      ? undefined
      : user?.personas?.includes(UserPersona.AGENT)
        ? ROUTES.AGENT.NOTIFICATION_PREFERENCES
        : ROUTES.PORTAL.NOTIFICATION_PREFERENCES;

  const sidebarNavProps: Omit<SidebarNavProps, "showUserSection"> = {
    navItems,
    pathname,
    onNavItemClick: () => setSidebarOpen(false),
    user,
    initials,
    onLogout: handleLogout,
    isLoggingOut: logout.isPending,
  };

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Desktop sidebar — navigation only, no user section */}
      <aside
        className={`hidden lg:flex flex-col shrink-0 h-full bg-sidebar border-r border-sidebar-border transition-[width] duration-200 ${
          collapsed ? "w-17" : "w-60"
        }`}
      >
        <SidebarNav {...sidebarNavProps} showUserSection={false} collapsed={collapsed} />
        <div className={`border-t border-sidebar-border ${collapsed ? "p-2" : "p-3"}`}>
          <button
            onClick={toggleCollapsed}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm font-medium text-sidebar-foreground hover:text-sidebar-foreground-active hover:bg-white/5 transition-colors duration-150"
          >
            {collapsed ? (
              <ChevronsRight className="w-4 h-4" strokeWidth={1.75} />
            ) : (
              <>
                <ChevronsLeft className="w-4 h-4" strokeWidth={1.75} />
                Collapse
              </>
            )}
          </button>
        </div>
      </aside>

      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div
          className="lg:hidden fixed inset-0 z-40 bg-black/50"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Mobile sidebar drawer — includes user section, never collapses */}
      <aside
        className="lg:hidden fixed inset-y-0 left-0 z-50 w-64 flex flex-col bg-sidebar border-r border-sidebar-border transform transition-transform duration-300"
        style={{ transform: sidebarOpen ? "translateX(0)" : "translateX(-100%)" }}
      >
        <SidebarNav
          {...sidebarNavProps}
          showUserSection={true}
          onClose={() => setSidebarOpen(false)}
        />
      </aside>

      {/* Main content area */}
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        {/* Desktop top nav */}
        <header
          className="hidden lg:flex items-center justify-between px-6 h-14 shrink-0 bg-white border-b border-brand-outline-variant/12"
        >
          <TopNavBreadcrumb />
          <div className="flex items-center gap-1">
            <PortalSwitcher />
            <ChatButton />
            <NotificationBell />
            <TopNavUserMenu
              user={user}
              initials={initials}
              onLogout={handleLogout}
              isLoggingOut={logout.isPending}
              notificationPrefsHref={notificationPrefsHref}
            />
          </div>
        </header>

        {/* Mobile header */}
        <header
          className="lg:hidden flex items-center gap-3 px-4 py-3 shrink-0 border-b border-brand-outline-variant/12 bg-white"
        >
          <button
            onClick={() => setSidebarOpen(true)}
            aria-label="Open menu"
            className="p-1.5 rounded-lg hover:bg-gray-100 transition-colors text-brand-navy"
          >
            <Menu className="w-5 h-5" />
          </button>
          <div className="flex items-center flex-1">
            <BrandLogo variant="dark" size="sm" />
          </div>
          <div className="flex items-center gap-1">
            <PortalSwitcher />
            <ChatButton />
            <NotificationBell />
            <div
              className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold bg-brand-viridian/12 text-brand-viridian"
            >
              {initials}
            </div>
          </div>
        </header>

        {/* Scrollable main */}
        <main className="flex-1 overflow-y-auto bg-brand-surface-low">
          {children}
        </main>
      </div>
    </div>
  );
}
