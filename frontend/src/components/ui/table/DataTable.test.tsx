import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import type { Page } from "@/types/models";

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/admin/test",
}));

import { DataTable, datatableActionTestId } from "./DataTable";

type Row = { id: string; name: string };

const PAGE = {
  items: [
    { id: "row-1", name: "First" },
    { id: "row-2", name: "Second" },
  ],
  meta: { page: 0, pageSize: 2, count: 2, total: 4, totalPages: 2, prevPage: null, nextPage: 1 },
} as unknown as Page<Row>;

function renderTable() {
  return renderToStaticMarkup(
    <DataTable<Row>
      dataPage={PAGE}
      columns={[{ key: "name", label: "Name" }]}
      actions={[{ label: "Approve payout", onClick: vi.fn() }]}
      currentPage={0}
      updateFilters={vi.fn()}
      isLoading={false}
      isError={false}
      error={null}
    />,
  );
}

// Stable anchors let browser specs target a row, its actions and paging without leaning on
// visible copy or DOM position — the same anchors on every admin table.
describe("DataTable automation anchors", () => {
  it("marks every row with a stable test id and the row's own id", () => {
    const html = renderTable();

    expect(html.match(/data-testid="datatable-row"/g)).toHaveLength(2);
    expect(html).toContain('data-row-id="row-1"');
    expect(html).toContain('data-row-id="row-2"');
  });

  it("gives each row's actions trigger a test id and an accessible name", () => {
    const html = renderTable();

    expect(html.match(/data-testid="datatable-row-actions"/g)).toHaveLength(2);
    expect(html).toMatch(/aria-label="Row actions"/);
  });

  it("anchors the pagination controls", () => {
    const html = renderTable();

    expect(html).toContain('data-testid="datatable-prev"');
    expect(html).toContain('data-testid="datatable-next"');
  });

  it("derives each action menu item's test id from its label", () => {
    expect(datatableActionTestId("Approve payout")).toBe("datatable-action-approve-payout");
    expect(datatableActionTestId("  Hold / Review ")).toBe("datatable-action-hold-review");
  });
});
