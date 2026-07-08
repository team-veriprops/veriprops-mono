import { ReactNode } from "react";
import { cn } from "@lib/utils";
import PageHeader from "./PageHeader";

type ShellWidth = "narrow" | "default" | "wide";

const MAX_WIDTH: Record<ShellWidth, string> = {
  narrow: "max-w-3xl",
  default: "max-w-4xl",
  wide: "max-w-5xl",
};

interface PageShellProps {
  title: string;
  description?: string;
  /** Right-aligned header actions. */
  actions?: ReactNode;
  /** Attention-chip row under the header. */
  meta?: ReactNode;
  width?: ShellWidth;
  className?: string;
  "data-testid"?: string;
  children: ReactNode;
}

/**
 * Standard inner content wrapper for a page: the centered max-width container plus a
 * PageHeader. Consolidates the `mx-auto max-w-* space-y-6 p-4 sm:p-6` boilerplate the
 * dashboards and admin surfaces each hand-rolled. This is content-only — it does not
 * touch AppShell / the nav sidebar.
 */
export function PageShell({
  title,
  description,
  actions,
  meta,
  width = "default",
  className,
  children,
  ...rest
}: PageShellProps) {
  return (
    <div
      className={cn("mx-auto w-full space-y-6 p-4 sm:p-6", MAX_WIDTH[width], className)}
      data-testid={rest["data-testid"]}
    >
      <PageHeader title={title} description={description} actions={actions} meta={meta} />
      {children}
    </div>
  );
}
