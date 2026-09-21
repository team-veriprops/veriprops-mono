"use client";

import { Button } from "@3rdparty/ui/button";
import { cn } from "@lib/utils";

interface ListPagerProps {
  /** Zero-indexed, as the backend pages. */
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  className?: string;
  /** Prefix for the controls' test ids: `${testIdPrefix}-prev`, `-next`, `-label`. */
  testIdPrefix?: string;
}

/**
 * Previous / next paging for a server-paged list that is not a DataTable (a history, an
 * inbox). Renders nothing for a single page.
 */
export default function ListPager({
  page,
  totalPages,
  onPageChange,
  className,
  testIdPrefix = "list-pager",
}: ListPagerProps) {
  if (totalPages <= 1) return null;

  return (
    <div className={cn("flex items-center justify-between gap-3", className)}>
      <Button
        variant="outline"
        disabled={page <= 0}
        onClick={() => onPageChange(Math.max(0, page - 1))}
        data-testid={`${testIdPrefix}-prev`}
      >
        Previous
      </Button>
      <span className="text-xs text-brand-on-surface-variant" data-testid={`${testIdPrefix}-label`}>
        Page {page + 1} of {totalPages}
      </span>
      <Button
        variant="outline"
        disabled={page + 1 >= totalPages}
        onClick={() => onPageChange(page + 1)}
        data-testid={`${testIdPrefix}-next`}
      >
        Next
      </Button>
    </div>
  );
}
