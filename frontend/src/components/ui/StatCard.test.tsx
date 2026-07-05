import { describe, it, expect } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { StatCard } from "./StatCard";

describe("StatCard", () => {
  it("renders the backend-provided label and value", () => {
    const html = renderToStaticMarkup(<StatCard label="Overdue" value={7} />);
    expect(html).toContain("Overdue");
    expect(html).toContain("7");
  });

  it("wraps the tile in a link when href is set", () => {
    const html = renderToStaticMarkup(<StatCard label="Verifications" value={3} href="/admin/verifications" />);
    expect(html).toContain('href="/admin/verifications"');
  });

  it("renders a plain tile (no anchor) without href", () => {
    const html = renderToStaticMarkup(<StatCard label="Submitted" value={0} />);
    expect(html).not.toContain("<a ");
  });
});
