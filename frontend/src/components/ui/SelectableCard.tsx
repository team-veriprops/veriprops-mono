"use client";

import { ReactNode } from "react";
import { Check, LucideIcon } from "lucide-react";
import { cn } from "@lib/utils";

interface SelectableCardProps {
  /** Whether this option is currently chosen. */
  selected: boolean;
  /** Toggle/choose this option. */
  onSelect: () => void;
  icon: LucideIcon;
  title: ReactNode;
  description?: ReactNode;
  /** Small inline pill rendered next to the title (e.g. "Recommended"). */
  badge?: ReactNode;
  /** Block content below the description (e.g. a licence-required pill). */
  footer?: ReactNode;
  /**
   * ARIA/interaction semantics: "radio" for single-select groups,
   * "checkbox" for multi-select. Drives the exposed role + aria-checked.
   */
  selectionMode: "radio" | "checkbox";
  /** Show a check badge in the top-right when selected (defaults on for checkbox). */
  showCheck?: boolean;
  testId?: string;
  className?: string;
}

/**
 * The platform's canonical "pick an option" tile: an icon in a rounded tile,
 * a title/description, and a primary-colored selection ring. Used by the
 * submission and agent-onboarding wizards for property type, agent role, and
 * KYC method — keep new card-style choosers on this rather than re-rolling the
 * markup.
 */
export function SelectableCard({
  selected,
  onSelect,
  icon: Icon,
  title,
  description,
  badge,
  footer,
  selectionMode,
  showCheck = selectionMode === "checkbox",
  testId,
  className,
}: SelectableCardProps) {
  return (
    <button
      type="button"
      role={selectionMode}
      aria-checked={selected}
      onClick={onSelect}
      data-testid={testId}
      className={cn(
        "relative flex items-start gap-3 rounded-xl border p-4 text-left transition-all",
        selected
          ? "border-primary bg-primary/5 ring-1 ring-primary"
          : "border-border hover:border-primary/40 hover:bg-accent",
        className,
      )}
    >
      <span
        className={cn(
          "flex size-10 shrink-0 items-center justify-center rounded-lg",
          selected ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground",
        )}
      >
        <Icon className="size-5" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-2 font-semibold text-foreground">
          {title}
          {badge}
        </span>
        {description && <span className="block text-sm text-muted-foreground">{description}</span>}
        {footer}
      </span>
      {showCheck && selected && (
        <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
          <Check className="size-3.5" />
        </span>
      )}
    </button>
  );
}
