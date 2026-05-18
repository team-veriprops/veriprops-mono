"use client";

import { useState } from "react";
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
  CheckCircle2, LogOut, Menu, X
} from "lucide-react";
import NotificationBell from "@components/shared/notifications/NotificationBell";
import { useLogoutMutation } from "@components/website/auth/libs/useAuthQueries";
import { useAuthStore } from "@components/website/auth/libs/useAuthStore";
import { UserType, UserPersona, type AuthUser } from "@components/website/auth/models";
import { NavItem } from "@/components/nav/MenuSidebar";
import { ROUTES } from "@lib/routes";
import TopNavBreadcrumb from "@components/ui/TopNav/TopNavBreadcrumb";
import TopNavUserMenu from "@components/ui/TopNav/TopNavUserMenu";

interface AppShellProps {
  navItems: NavItem[];
  children: React.ReactNode;
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
}: SidebarNavProps) {
  return (
    <div className="flex flex-col h-full">
      {/* Logo */}
      <Link href={ROUTES.HOME} className="px-6 py-5 flex items-center gap-2.5" style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
        <div className="w-7 h-7 rounded-md flex items-center justify-center signature-gradient">
          <CheckCircle2 className="w-4 h-4 text-white" strokeWidth={2.5} />
        </div>
        <span className="text-base font-extrabold tracking-tight font-display" style={{ color: "#fff" }}>
          Veriprops
        </span>
      </Link>

      {/* Nav items */}
      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
        {navItems.map((item) => {
          const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`);
          const Icon = iconMap[item.icon];

          if (!Icon) return null;

          return (
            <div key={item.href}>
              <Link
                href={item.href}
                onClick={onNavItemClick}
                className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150"
                style={isActive
                  ? { backgroundColor: "rgba(63,102,83,0.2)", color: "#a5d0b9", border: "1px solid rgba(63,102,83,0.2)" }
                  : { color: "rgba(255,255,255,0.55)", border: "1px solid transparent" }}
                onMouseEnter={(e) => {
                  if (!isActive) (e.currentTarget as HTMLElement).style.color = "rgba(255,255,255,0.9)";
                }}
                onMouseLeave={(e) => {
                  if (!isActive) (e.currentTarget as HTMLElement).style.color = "rgba(255,255,255,0.55)";
                }}
              >
                <Icon className="w-4 h-4 flex-shrink-0" strokeWidth={isActive ? 2.5 : 1.75} />
                {item.title}
              </Link>
              {item.has_separator_after && (
                <div className="my-2 mx-3" style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }} />
              )}
            </div>
          );
        })}
      </nav>

      {/* User + logout — mobile drawer only */}
      {showUserSection && (
        <div className="px-4 py-4" style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}>
          <div className="flex items-center gap-3 mb-3 px-1">
            <Link
              href={ROUTES.ACCOUNT.SECURITY}
              onClick={onNavItemClick}
              className="flex items-center gap-3 flex-1 min-w-0 group"
            >
              <div
                className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 text-xs font-bold transition-opacity group-hover:opacity-80"
                style={{ backgroundColor: "rgba(63,102,83,0.25)", color: "#a5d0b9" }}
              >
                {initials}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-semibold truncate group-hover:underline" style={{ color: "#fff" }}>
                  {user ? `${user.firstName} ${user.lastName}` : "Loading..."}
                </div>
                <div className="text-xs truncate" style={{ color: "rgba(255,255,255,0.4)" }}>
                  {user?.email ?? ""}
                </div>
              </div>
            </Link>
            <div className="flex-shrink-0">
              <NotificationBell dark />
            </div>
          </div>
          <button
            onClick={onLogout}
            disabled={isLoggingOut}
            className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-150 hover:bg-white/5"
            style={{ color: "rgba(255,255,255,0.45)" }}
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
        className="hidden lg:flex flex-col w-60 flex-shrink-0 h-full"
        style={{ backgroundColor: "var(--brand-navy)", borderRight: "1px solid rgba(255,255,255,0.06)" }}
      >
        <SidebarNav {...sidebarNavProps} showUserSection={false} />
      </aside>

      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div
          className="lg:hidden fixed inset-0 z-40"
          style={{ backgroundColor: "rgba(0,0,0,0.5)" }}
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Mobile sidebar drawer — includes user section */}
      <aside
        className="lg:hidden fixed inset-y-0 left-0 z-50 w-64 flex flex-col transform transition-transform duration-300"
        style={{
          backgroundColor: "var(--brand-navy)",
          borderRight: "1px solid rgba(255,255,255,0.06)",
          transform: sidebarOpen ? "translateX(0)" : "translateX(-100%)",
        }}
      >
        <div className="absolute top-4 right-4">
          <button onClick={() => setSidebarOpen(false)} style={{ color: "rgba(255,255,255,0.5)" }}>
            <X className="w-5 h-5" />
          </button>
        </div>
        <SidebarNav {...sidebarNavProps} showUserSection={true} />
      </aside>

      {/* Main content area */}
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        {/* Desktop top nav */}
        <header
          className="hidden lg:flex items-center justify-between px-6 h-14 flex-shrink-0"
          style={{
            backgroundColor: "#fff",
            borderBottom: "1px solid rgba(196,198,207,0.12)",
          }}
        >
          <TopNavBreadcrumb />
          <div className="flex items-center gap-1">
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
          className="lg:hidden flex items-center gap-4 px-4 py-3 flex-shrink-0"
          style={{ borderBottom: "1px solid rgba(196,198,207,0.12)", backgroundColor: "#fff" }}
        >
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
            style={{ color: "var(--brand-navy)" }}
          >
            <Menu className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-2 flex-1">
            <div className="w-6 h-6 rounded-md flex items-center justify-center signature-gradient">
              <CheckCircle2 className="w-3.5 h-3.5 text-white" strokeWidth={2.5} />
            </div>
            <span className="text-sm font-bold font-display" style={{ color: "var(--brand-navy)" }}>
              Veriprops
            </span>
          </div>
          <div className="flex items-center gap-1">
            <NotificationBell />
            <div
              className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold"
              style={{ backgroundColor: "rgba(63,102,83,0.12)", color: "var(--brand-viridian)" }}
            >
              {initials}
            </div>
          </div>
        </header>

        {/* Scrollable main */}
        <main className="flex-1 overflow-y-auto" style={{ backgroundColor: "var(--brand-surface-low)" }}>
          {children}
        </main>
      </div>
    </div>
  );
}
