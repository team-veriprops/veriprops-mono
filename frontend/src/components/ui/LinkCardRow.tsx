import { ReactNode } from "react";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { Card } from "@3rdparty/ui/card";
import { cn } from "@lib/utils";

interface LinkCardRowProps {
  href: string;
  title: ReactNode;
  subtitle?: ReactNode;
  /** Trailing content before the chevron (e.g. a status badge). */
  trailing?: ReactNode;
  className?: string;
  "data-testid"?: string;
}

/**
 * A clickable list row rendered as a card: title + subtitle on the left, an optional
 * trailing slot, and a ChevronRight link affordance. Shared by the admin and portal
 * dashboards' "recent" lists so they stay identical.
 */
export function LinkCardRow({ href, title, subtitle, trailing, className, ...rest }: LinkCardRowProps) {
  return (
    <Link href={href} data-testid={rest["data-testid"]}>
      <Card className={cn("flex items-center justify-between gap-3 p-4 transition hover:border-primary", className)}>
        <div className="min-w-0 space-y-1">
          <p className="truncate font-medium">{title}</p>
          {subtitle ? <p className="text-xs text-muted-foreground">{subtitle}</p> : null}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {trailing}
          <ChevronRight className="size-4 text-muted-foreground" aria-hidden />
        </div>
      </Card>
    </Link>
  );
}
