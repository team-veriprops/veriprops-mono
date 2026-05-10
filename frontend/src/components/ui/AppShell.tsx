"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard,
  UserCog,
  ClipboardList,
  AlertTriangle,
  MessageSquare,
  UserRoundKey,
  Settings,
  HelpCircle,
  FileCheck,
  CreditCard,
  CheckCircle2, LogOut, Menu, X
} from "lucide-react";
import { useLogoutMutation } from "@components/website/auth/libs/useAuthQueries";
import { useAuthStore } from "@components/website/auth/libs/useAuthStore";
import { NavItem } from "@/components/nav/MenuSidebar";
import { ROUTES } from "@lib/routes";

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
} as const;

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

  const NavContent = () => (
    <div className="flex flex-col h-full">
      {/* Logo */}
      <div className="px-6 py-5 flex items-center gap-2.5" style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
        <div className="w-7 h-7 rounded-md flex items-center justify-center signature-gradient">
          <CheckCircle2 className="w-4 h-4 text-white" strokeWidth={2.5} />
        </div>
        <span className="text-base font-extrabold tracking-tight font-display" style={{ color: "#fff" }}>
          Veriprops
        </span>
      </div>

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
                onClick={() => setSidebarOpen(false)}
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

      {/* User + logout */}
      <div className="px-4 py-4" style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}>
        <div className="flex items-center gap-3 mb-3 px-1">
          <div
            className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 text-xs font-bold"
            style={{ backgroundColor: "rgba(63,102,83,0.25)", color: "#a5d0b9" }}
          >
            {initials}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-semibold truncate" style={{ color: "#fff" }}>
              {user ? `${user.firstName} ${user.lastName}` : "Loading..."}
            </div>
            <div className="text-xs truncate" style={{ color: "rgba(255,255,255,0.4)" }}>
              {user?.email ?? ""}
            </div>
          </div>
        </div>
        <button
          onClick={handleLogout}
          disabled={logout.isPending}
          className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-150 hover:bg-white/5"
          style={{ color: "rgba(255,255,255,0.45)" }}
        >
          <LogOut className="w-4 h-4" strokeWidth={1.75} />
          {logout.isPending ? "Signing out…" : "Sign out"}
        </button>
      </div>
    </div>
  );

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Desktop sidebar */}
      <aside
        className="hidden lg:flex flex-col w-60 flex-shrink-0 h-full"
        style={{ backgroundColor: "var(--brand-navy)", borderRight: "1px solid rgba(255,255,255,0.06)" }}
      >
        <NavContent />
      </aside>

      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div
          className="lg:hidden fixed inset-0 z-40"
          style={{ backgroundColor: "rgba(0,0,0,0.5)" }}
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Mobile sidebar drawer */}
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
        <NavContent />
      </aside>

      {/* Main content area */}
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
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
          <div
            className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold"
            style={{ backgroundColor: "rgba(63,102,83,0.12)", color: "var(--brand-viridian)" }}
          >
            {initials}
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
