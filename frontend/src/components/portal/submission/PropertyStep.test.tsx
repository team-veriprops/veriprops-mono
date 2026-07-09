import { describe, it, expect, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { PropertyKind } from "@/types/verification";
import { EMPTY_SUBMISSION } from "./types";

// Geo autocomplete rides TanStack Query — stub it so the component renders without a provider.
vi.mock("@components/portal/libs/useVerificationQueries", () => ({
  useGeoAutocompleteQuery: () => ({ data: [] }),
}));

import PropertyStep from "./PropertyStep";

function render(kind: PropertyKind): string {
  return renderToStaticMarkup(
    <PropertyStep
      value={{ ...EMPTY_SUBMISSION.property, propertyType: kind }}
      onChange={() => {}}
    />,
  );
}

describe("PropertyStep", () => {
  it("always offers both property-type cards", () => {
    const html = render(PropertyKind.LAND);
    expect(html).toContain("verify-new-type-land");
    expect(html).toContain("verify-new-type-building");
  });

  it("shows land-specific detail fields for LAND (PRD §5.1)", () => {
    const html = render(PropertyKind.LAND);
    expect(html).toContain("About the land");
    expect(html).toContain("verify-new-land-use");
    expect(html).toContain("verify-new-survey-status");
    expect(html).toContain("verify-new-land-size");
    // Building-only fields must not leak into the Land view.
    expect(html).not.toContain("verify-new-occupancy");
  });

  it("shows building-specific detail fields for BUILDING (PRD §5.1)", () => {
    const html = render(PropertyKind.BUILDING);
    expect(html).toContain("About the building");
    expect(html).toContain("verify-new-building-type");
    expect(html).toContain("verify-new-occupancy");
    expect(html).toContain("verify-new-floors");
    expect(html).toContain("verify-new-year-built");
    expect(html).not.toContain("verify-new-land-use");
  });

  it("marks the active type card as checked", () => {
    const land = render(PropertyKind.LAND);
    // The land card exposes aria-checked when LAND is selected (radio semantics).
    expect(land).toMatch(/verify-new-type-land[\s\S]*?aria-checked="true"|aria-checked="true"[\s\S]*?verify-new-type-land/);
  });
});
