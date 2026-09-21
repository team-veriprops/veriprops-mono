import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import { PublicLookupState, PublicSummary } from "@/types/share";
import { PropertyKind, VerificationTier } from "@/types/verification";

import { PublicSummaryCard } from "./PublicSummaryCard";

function summary(overrides: Partial<PublicSummary> = {}): PublicSummary {
  return {
    state: PublicLookupState.SHARED,
    verified: true,
    vid: "VP-2026-7EF29D",
    trustBand: "Safe",
    tier: VerificationTier.STANDARD,
    propertyType: PropertyKind.LAND,
    stateRegion: "Lagos",
    lga: "Eti-Osa",
    reportVersion: 1,
    reportDate: "2026-09-16",
    ...overrides,
  };
}

describe("PublicSummaryCard", () => {
  /**
   * This card and the owner's report show the same verdict and must show it the same way
   * (§10.2 parity), so both read the band's presentation from one shared mapping. The palette
   * shades this replaced failed WCAG AA — emerald-600 measured 3.50:1 against the report panel
   * and roughly 3.7:1 on this card's white background, where AA needs 4.5:1.
   */
  it("styles the band with the shared semantic token, not a palette colour", () => {
    const html = renderToStaticMarkup(<PublicSummaryCard summary={summary()} />);

    expect(html).toContain("text-success");
    expect(html).not.toMatch(/emerald|amber|text-red-\d/);
  });

  it("styles each band the customer can be given", () => {
    expect(renderToStaticMarkup(<PublicSummaryCard summary={summary({ trustBand: "Caution" })} />))
      .toContain("text-warning");
    expect(renderToStaticMarkup(<PublicSummaryCard summary={summary({ trustBand: "High Risk" })} />))
      .toContain("text-danger");
  });

  /** The allow-list is the point of this surface: the number never leaves the owner's report. */
  it("shows the band but never a numeric score", () => {
    const html = renderToStaticMarkup(<PublicSummaryCard summary={summary()} />);

    expect(html).toContain("Safe");
    expect(html).toContain("VP-2026-7EF29D");
    expect(html).not.toMatch(/\b\d{1,3}\s*\/\s*100\b/);
  });

  it("renders a neutral notice for a verification that is not shared", () => {
    const html = renderToStaticMarkup(
      <PublicSummaryCard
        summary={summary({ state: PublicLookupState.PRIVATE, message: "Not available." })}
      />,
    );

    expect(html).toContain("Not available.");
    expect(html).not.toContain("VP-2026-7EF29D");
  });
});
