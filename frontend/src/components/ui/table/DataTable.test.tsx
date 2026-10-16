import { describe, expect, it, vi } from "vitest";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";

import type { Page } from "@/types/models";

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/admin/test",
}));

import { DataTable, datatableActionTestId, datatableSortTestId, type TableFilterUpdate } from "./DataTable";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

type Row = { id: string; name: string; email: string };

const PAGE = {
  items: [
    { id: "row-1", name: "First", email: "a@x.io" },
    { id: "row-2", name: "Second", email: "b@x.io" },
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

// Which headers sort is the backend's call (`meta.sortableFields`); the table only offers those,
// shows the order in force, and asks the backend for the next one.
describe("DataTable server-driven sorting", () => {
  const SORTED = {
    ...PAGE,
    meta: { ...PAGE.meta, sort: "email asc", sortableFields: ["email"] },
  } as unknown as Page<Row>;
  const COLUMNS = [
    { key: "name", label: "Name" },
    { key: "email", label: "Email" },
  ];

  function mount(updateFilters: (updates: TableFilterUpdate) => void, orderBy?: string) {
    const host = document.createElement("div");
    const root = createRoot(host);
    act(() =>
      root.render(
        <DataTable<Row>
          dataPage={SORTED}
          columns={COLUMNS}
          orderBy={orderBy}
          currentPage={0}
          updateFilters={updateFilters}
          isLoading={false}
          isError={false}
          error={null}
        />,
      ),
    );
    return { host, unmount: () => act(() => root.unmount()) };
  }

  it("offers only the backend's sortable columns, showing the sort in force", () => {
    const { host, unmount } = mount(vi.fn());

    const email = host.querySelector(`[data-testid="${datatableSortTestId("email")}"]`);
    expect(email?.getAttribute("aria-sort")).toBe("ascending");
    expect(host.querySelector(`[data-testid="${datatableSortTestId("name")}"]`)).toBeNull();
    unmount();
  });

  it("asks for the next order of a clicked column and returns to the first page", () => {
    const updateFilters = vi.fn();
    const { host, unmount } = mount(updateFilters);

    act(() => (host.querySelector(`[data-testid="${datatableSortTestId("email")}"]`) as HTMLElement).click());

    expect(updateFilters).toHaveBeenCalledWith({ orderBy: "email desc", page: 0 });
    unmount();
  });

  it("an explicit orderBy wins over the backend's default for the arrow", () => {
    const { host, unmount } = mount(vi.fn(), "email desc");

    expect(
      host.querySelector(`[data-testid="${datatableSortTestId("email")}"]`)?.getAttribute("aria-sort"),
    ).toBe("descending");
    unmount();
  });
});
