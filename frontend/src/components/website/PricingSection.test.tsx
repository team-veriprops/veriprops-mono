import { describe, it, expect } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import type { PublicPricingTier } from "@/types/models";
import { VerificationTier } from "@/types/verification";

import PricingSection from "./PricingSection";

// Backend prices arrive in kobo (minor units).
const BACKEND_PRICES: PublicPricingTier[] = [
  { tier: VerificationTier.BASIC, priceNgnMinor: 5_200_000 },
  { tier: VerificationTier.STANDARD, priceNgnMinor: 12_000_000 },
  { tier: VerificationTier.PREMIUM, priceNgnMinor: 30_000_000 },
];

const NAIRA_FIGURE = /₦\d/g;

describe("PricingSection", () => {
  it("renders the backend's tier prices from props, so the server HTML and hydration agree", () => {
    const html = renderToStaticMarkup(<PricingSection prices={BACKEND_PRICES} />);

    expect(html).toContain("₦52k");
    expect(html).toContain("₦120k");
    expect(html).toContain("₦300k");
  });

  it("shows no figure for a tier the backend did not price — never a hardcoded fallback", () => {
    const html = renderToStaticMarkup(
      <PricingSection prices={BACKEND_PRICES.filter((p) => p.tier === VerificationTier.STANDARD)} />,
    );

    expect(html).toContain("₦120k");
    expect(html.match(NAIRA_FIGURE)).toHaveLength(1);
  });

  it("still renders every tier card when no prices are available", () => {
    const html = renderToStaticMarkup(<PricingSection prices={[]} />);

    expect(html).not.toMatch(NAIRA_FIGURE);
    for (const name of ["Basic", "Standard", "Premium"]) {
      expect(html).toContain(name);
    }
  });
});
