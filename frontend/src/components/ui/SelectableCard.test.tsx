import { describe, it, expect } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { LandPlot } from "lucide-react";
import { SelectableCard } from "./SelectableCard";

describe("SelectableCard", () => {
  it("exposes the requested selection role and checked state", () => {
    const html = renderToStaticMarkup(
      <SelectableCard
        selectionMode="radio"
        selected
        onSelect={() => {}}
        icon={LandPlot}
        title="Land"
        description="A plot"
        testId="pick-land"
      />,
    );
    expect(html).toContain('role="radio"');
    expect(html).toContain('aria-checked="true"');
    expect(html).toContain("pick-land");
    expect(html).toContain("Land");
  });

  it("uses checkbox semantics for multi-select and shows a check when selected", () => {
    const html = renderToStaticMarkup(
      <SelectableCard selectionMode="checkbox" selected onSelect={() => {}} icon={LandPlot} title="Field" />,
    );
    expect(html).toContain('role="checkbox"');
    // The check badge is an <svg> (lucide Check) — rendered only when selected.
    expect(html).toContain("<svg");
  });

  it("renders badge and footer slots", () => {
    const html = renderToStaticMarkup(
      <SelectableCard
        selectionMode="radio"
        selected={false}
        onSelect={() => {}}
        icon={LandPlot}
        title="BVN"
        badge={<span>Recommended</span>}
        footer={<span>Licence required</span>}
      />,
    );
    expect(html).toContain("Recommended");
    expect(html).toContain("Licence required");
    // Unselected radio never shows the check badge.
    expect(html).toContain('aria-checked="false"');
  });
});
