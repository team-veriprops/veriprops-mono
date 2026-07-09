import { describe, it, expect } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { LinkCardRow } from "./LinkCardRow";

describe("LinkCardRow", () => {
  it("links to href and renders title, subtitle, trailing, and a chevron", () => {
    const html = renderToStaticMarkup(
      <LinkCardRow
        href="/portal/verifications/1"
        title="12 Marina Road"
        subtitle="VP-1 · Standard"
        trailing={<span>Completed</span>}
        data-testid="recent-1"
      />,
    );
    expect(html).toContain('href="/portal/verifications/1"');
    expect(html).toContain("12 Marina Road");
    expect(html).toContain("VP-1");
    expect(html).toContain("Completed");
    expect(html).toContain("lucide-chevron-right");
    expect(html).toContain("recent-1");
  });
});
