import { describe, it, expect } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { ClipboardList } from "lucide-react";
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

  it("shows a link-affordance icon only when the tile links somewhere", () => {
    const linked = renderToStaticMarkup(
      <StatCard label="Total" value={5} icon={ClipboardList} href="/x" />,
    );
    const plain = renderToStaticMarkup(<StatCard label="Total" value={5} icon={ClipboardList} />);
    // The linked tile carries the arrow-up-right affordance; the plain tile does not.
    expect(linked).toContain("lucide-arrow-up-right");
    expect(plain).not.toContain("lucide-arrow-up-right");
  });
});
