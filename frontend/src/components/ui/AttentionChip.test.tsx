import { describe, it, expect } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { Clock } from "lucide-react";
import { AttentionChip } from "./AttentionChip";

describe("AttentionChip", () => {
  it("renders its content and icon", () => {
    const html = renderToStaticMarkup(<AttentionChip icon={Clock}>3 payouts pending</AttentionChip>);
    expect(html).toContain("3 payouts pending");
    expect(html).toContain("<svg");
  });

  it("links and shows the link affordance when href is set", () => {
    const linked = renderToStaticMarkup(<AttentionChip href="/admin/finance/payouts">Pending</AttentionChip>);
    const plain = renderToStaticMarkup(<AttentionChip>Pending</AttentionChip>);
    expect(linked).toContain('href="/admin/finance/payouts"');
    expect(linked).toContain("lucide-arrow-up-right");
    expect(plain).not.toContain("lucide-arrow-up-right");
  });
});
