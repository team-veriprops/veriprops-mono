import { describe, it, expect } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { MiniBarBreakdown } from "./MiniBarBreakdown";

describe("MiniBarBreakdown", () => {
  it("renders a humanized, tone-coded bar per status with its count", () => {
    const html = renderToStaticMarkup(
      <MiniBarBreakdown counts={{ PAID: 120, PENDING: 8 }} />,
    );
    expect(html).toContain("Paid");
    expect(html).toContain("Pending");
    expect(html).toContain("120");
    expect(html).toContain("8");
    expect(html).not.toContain(">PAID<");
  });

  it("shows the empty text when there are no counts", () => {
    const html = renderToStaticMarkup(<MiniBarBreakdown counts={{}} emptyText="No payments." />);
    expect(html).toContain("No payments.");
  });
});
