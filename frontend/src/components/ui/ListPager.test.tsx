import { describe, expect, it, vi } from "vitest";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import ListPager from "./ListPager";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const noop = () => {};

/** The `<button>` tag carrying a test id, for asserting its attributes. */
function buttonTag(html: string, testId: string): string {
  return html.match(new RegExp(`<button[^>]*data-testid="${testId}"[^>]*>`))?.[0] ?? "";
}

describe("ListPager", () => {
  it("renders nothing for a single page", () => {
    expect(renderToStaticMarkup(<ListPager page={0} totalPages={1} onPageChange={noop} />)).toBe("");
  });

  it("shows the one-based page under the given test id prefix", () => {
    const html = renderToStaticMarkup(
      <ListPager page={1} totalPages={3} onPageChange={noop} testIdPrefix="inbox" />,
    );

    expect(html).toContain("Page 2 of 3");
    expect(buttonTag(html, "inbox-prev")).not.toContain('disabled=""');
    expect(buttonTag(html, "inbox-next")).not.toContain('disabled=""');
  });

  it("disables the ends", () => {
    const first = renderToStaticMarkup(<ListPager page={0} totalPages={2} onPageChange={noop} />);
    const last = renderToStaticMarkup(<ListPager page={1} totalPages={2} onPageChange={noop} />);

    expect(buttonTag(first, "list-pager-prev")).toContain('disabled=""');
    expect(buttonTag(last, "list-pager-next")).toContain('disabled=""');
  });

  it("keeps a table footer in place on a single page", () => {
    const html = renderToStaticMarkup(
      <ListPager page={0} totalPages={0} onPageChange={noop} testIdPrefix="datatable" alwaysShow />,
    );

    expect(html).toContain("Page 1 of 1");
    expect(buttonTag(html, "datatable-prev")).toContain('disabled=""');
    expect(buttonTag(html, "datatable-next")).toContain('disabled=""');
  });

  it("steps a page past the end back to the last page", () => {
    const onPageChange = vi.fn();
    const host = document.createElement("div");
    const root = createRoot(host);

    act(() => root.render(<ListPager page={7} totalPages={3} onPageChange={onPageChange} />));
    act(() => root.unmount());

    expect(onPageChange).toHaveBeenCalledWith(2);
  });

  it("leaves an in-range page alone", () => {
    const onPageChange = vi.fn();
    const host = document.createElement("div");
    const root = createRoot(host);

    act(() => root.render(<ListPager page={0} totalPages={0} onPageChange={onPageChange} />));
    act(() => root.unmount());

    expect(onPageChange).not.toHaveBeenCalled();
  });
});
