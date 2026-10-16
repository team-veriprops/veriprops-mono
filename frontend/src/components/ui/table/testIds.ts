/**
 * Automation anchors shared by every admin DataTable. Kept free of React so the Playwright
 * helpers can import the same derivation the component renders, instead of re-implementing it.
 */

export const DATATABLE_TEST_IDS = {
  SEARCH: "datatable-search",
  ROW: "datatable-row",
  ROW_ACTIONS: "datatable-row-actions",
  PREV: "datatable-prev",
  NEXT: "datatable-next",
  LABEL: "datatable-label",
} as const;

/** The footer pager's test-id prefix; `ListPager` derives `PREV`/`NEXT` from it. */
export const DATATABLE_PAGER_PREFIX = "datatable";

/** The rows-per-page choices; the largest stays within every list endpoint's `page_size` cap (le=50). */
export const ROWS_PER_PAGE_OPTIONS = [5, 10, 20, 30, 50] as const;

/** Stable automation id for a sortable column header ("email" → `datatable-sort-email`). */
export function datatableSortTestId(key: string): string {
  return `datatable-sort-${key}`;
}

/**
 * Stable automation id for a row action's menu item, derived from its label
 * ("Approve payout" → `datatable-action-approve-payout`), so every admin table exposes the same
 * anchors without each consumer naming them.
 */
export function datatableActionTestId(label: string): string {
  const slug = label
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return `datatable-action-${slug}`;
}
