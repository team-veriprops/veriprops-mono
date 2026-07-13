"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ArrowLeftRight } from "lucide-react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@3rdparty/ui/dropdown-menu";
import { useAuthStore } from "@components/website/auth/libs/useAuthStore";
import { useCrossPortalSummaryQuery } from "@components/website/auth/libs/useAuthQueries";
import { UserPersona } from "@components/website/auth/models";
import { ROUTES } from "@lib/routes";
import { cn } from "@lib/utils";

const PERSONA_HOME: Record<UserPersona, { label: string; href: string }> = {
  [UserPersona.CUSTOMER]: { label: "Customer portal", href: ROUTES.PORTAL.DASHBOARD },
  [UserPersona.AGENT]: { label: "Agent portal", href: ROUTES.AGENT.DASHBOARD },
};

// Lets a user with more than one persona switch portals, with a badge counting
// items waiting in the other hat. Renders nothing for single-persona users.
export default function PortalSwitcher({ dark = false }: { dark?: boolean }) {
  const pathname = usePathname();
  const session = useAuthStore((s) => s.session);
  const personas = (session?.user?.personas ?? []) as UserPersona[];
  const multiPersona = personas.length >= 2;

  const { data } = useCrossPortalSummaryQuery(multiPersona);

  if (!multiPersona) return null;

  const current: UserPersona | null = pathname.startsWith("/agents")
    ? UserPersona.AGENT
    : pathname.startsWith("/portal")
      ? UserPersona.CUSTOMER
      : null;

  const counts = new Map<UserPersona, number>(
    (data?.personas ?? []).map((p) => [p.persona, p.actionableCount]),
  );
  const others = personas.filter((p) => p !== current);
  const otherTotal = others.reduce((sum, p) => sum + (counts.get(p) ?? 0), 0);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label="Switch portal"
        data-testid="portal-switch"
        data-other-count={otherTotal}
        className={cn(
          "relative w-9 h-9 rounded-lg flex items-center justify-center transition-colors duration-150 hover:bg-black/5",
          dark ? "text-white/80" : "text-brand-on-surface-variant"
        )}
      >
        <ArrowLeftRight className="w-5 h-5" aria-hidden="true" />
        {otherTotal > 0 && (
          <span
            data-testid="portal-switch-badge"
            className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 rounded-full text-[10px] font-bold flex items-center justify-center text-white bg-danger"
          >
            {otherTotal > 99 ? "99+" : otherTotal}
          </span>
        )}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {others.map((persona) => {
          const home = PERSONA_HOME[persona];
          const count = counts.get(persona) ?? 0;
          return (
            <DropdownMenuItem key={persona} asChild>
              <Link
                href={home.href}
                data-testid={`portal-switch-to-${persona}`}
                className="flex items-center justify-between gap-6"
              >
                <span>{home.label}</span>
                {count > 0 && (
                  <span
                    className="min-w-[18px] h-[18px] px-1 rounded-full text-[10px] font-bold flex items-center justify-center text-white bg-danger"
                  >
                    {count > 99 ? "99+" : count}
                  </span>
                )}
              </Link>
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
