/**
 * Automation anchors shared by every admin DataTable. Kept free of React so the Playwright
 * helpers can import the same derivation the component renders, instead of re-implementing it.
 */

export const DATATABLE_TEST_IDS = {
  ROW: "datatable-row",
  ROW_ACTIONS: "datatable-row-actions",
  PREV: "datatable-prev",
  NEXT: "datatable-next",
} as const;

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
