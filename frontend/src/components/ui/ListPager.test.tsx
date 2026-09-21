import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import ListPager from "./ListPager";

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
});
