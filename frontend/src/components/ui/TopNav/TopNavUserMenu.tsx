"use client";

import Link from "next/link";
import { Bell, LogOut, Settings } from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@3rdparty/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@3rdparty/ui/dropdown-menu";
import type { AuthUser } from "@components/website/auth/models";
import { ROUTES } from "@lib/routes";

interface TopNavUserMenuProps {
  user: AuthUser | null | undefined;
  initials: string;
  onLogout: () => void;
  isLoggingOut: boolean;
  notificationPrefsHref?: string;
}

export default function TopNavUserMenu({
  user,
  initials,
  onLogout,
  isLoggingOut,
  notificationPrefsHref,
}: TopNavUserMenuProps) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          className="rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          aria-label="User menu"
        >
          <Avatar className="size-8 cursor-pointer">
            {user?.avatarUrl && <AvatarImage src={user.avatarUrl} alt={`${user.firstName} ${user.lastName}`} />}
            <AvatarFallback
              className="text-xs font-bold bg-brand-viridian/12 text-brand-viridian"
            >
              {initials}
            </AvatarFallback>
          </Avatar>
        </button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" sideOffset={8} className="w-56">
        {/* Identity header */}
        <DropdownMenuLabel className="font-normal">
          <div className="flex items-center gap-2.5 py-0.5">
            <Avatar className="size-8 flex-shrink-0">
              {user?.avatarUrl && <AvatarImage src={user.avatarUrl} alt="" />}
              <AvatarFallback
                className="text-xs font-bold bg-brand-viridian/12 text-brand-viridian"
              >
                {initials}
              </AvatarFallback>
            </Avatar>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-brand-navy">
                {user ? `${user.firstName} ${user.lastName}` : "Loading…"}
              </p>
              <p className="truncate text-xs text-muted-foreground">
                {user?.email ?? ""}
              </p>
            </div>
          </div>
        </DropdownMenuLabel>

        <DropdownMenuSeparator />

        <DropdownMenuGroup>
          <DropdownMenuItem asChild>
            <Link href={ROUTES.ACCOUNT.SECURITY} className="flex items-center gap-2 cursor-pointer">
              <Settings className="size-4" />
              Account Settings
            </Link>
          </DropdownMenuItem>

          {notificationPrefsHref && (
            <DropdownMenuItem asChild>
              <Link href={notificationPrefsHref} className="flex items-center gap-2 cursor-pointer">
                <Bell className="size-4" />
                Notification Preferences
              </Link>
            </DropdownMenuItem>
          )}
        </DropdownMenuGroup>

        <DropdownMenuSeparator />

        <DropdownMenuItem
          onClick={onLogout}
          disabled={isLoggingOut}
          className="text-destructive focus:text-destructive cursor-pointer"
        >
          <LogOut className="size-4" />
          {isLoggingOut ? "Signing out…" : "Sign out"}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
