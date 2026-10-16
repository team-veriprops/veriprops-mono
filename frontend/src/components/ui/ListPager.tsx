"use client";

import { useEffect } from "react";
import { Button } from "@3rdparty/ui/button";
import { cn } from "@lib/utils";

interface ListPagerProps {
  /** Zero-indexed, as the backend pages. */
  page: number;
  /** The backend's `meta.totalPages` — never derived on the client. */
  totalPages: number;
  onPageChange: (page: number) => void;
  className?: string;
  /** Prefix for the controls' test ids: `${testIdPrefix}-prev`, `-next`, `-label`. */
  testIdPrefix?: string;
  /** Keep rendering on a single page (a table footer holds its place); otherwise hidden. */
  alwaysShow?: boolean;
}

/**
 * Previous / next paging for every server-paged list, the DataTable footer included.
 * A page past the end (a stale bookmark, rows deleted since) steps back to the last page.
 */
export default function ListPager({
  page,
  totalPages,
  onPageChange,
  className,
  testIdPrefix = "list-pager",
  alwaysShow = false,
}: ListPagerProps) {
  useEffect(() => {
    if (totalPages > 0 && page >= totalPages) onPageChange(totalPages - 1);
  }, [page, totalPages, onPageChange]);

  if (totalPages <= 1 && !alwaysShow) return null;

  return (
    <div className={cn("flex items-center justify-between gap-3", className)}>
      <Button
        variant="outline"
        size="sm"
        disabled={page <= 0}
        onClick={() => onPageChange(Math.max(0, page - 1))}
        data-testid={`${testIdPrefix}-prev`}
      >
        Previous
      </Button>
      <span className="text-xs text-muted-foreground" data-testid={`${testIdPrefix}-label`}>
        Page {page + 1} of {Math.max(totalPages, 1)}
      </span>
      <Button
        variant="outline"
        size="sm"
        disabled={page + 1 >= totalPages}
        onClick={() => onPageChange(page + 1)}
        data-testid={`${testIdPrefix}-next`}
      >
        Next
      </Button>
    </div>
  );
}
