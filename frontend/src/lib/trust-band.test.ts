import { describe, expect, it } from "vitest";

import { TRUST_BAND_NEUTRAL, trustBandStyle } from "./trust-band";

/**
 * The trust band is the report's headline verdict, and it shipped in raw palette colours that
 * fail WCAG AA against the panel behind them — measured at 3.50:1 (Safe), 2.83:1 (Caution) and
 * 4.48:1 (High Risk) where AA needs 4.5:1. The semantic tokens are chosen for contrast, so the
 * mapping is expressed in those and shared, rather than restated per surface: the owner's
 * report and the public share card must show the same verdict the same way (§10.2 parity).
 */
describe("trustBandStyle", () => {
  it("styles every band with a semantic token rather than a raw palette colour", () => {
    expect(trustBandStyle("Safe").text).toBe("text-success");
    expect(trustBandStyle("Caution").text).toBe("text-warning");
    expect(trustBandStyle("High Risk").text).toBe("text-danger");
  });

  it("colours the gauge arc from the same token, so it follows the theme", () => {
    expect(trustBandStyle("Safe").stroke).toBe("stroke-success");
    expect(trustBandStyle("Caution").stroke).toBe("stroke-warning");
    expect(trustBandStyle("High Risk").stroke).toBe("stroke-danger");
  });

  it("tints the panel from that token too", () => {
    expect(trustBandStyle("Safe").tint).toContain("bg-success/");
    expect(trustBandStyle("High Risk").tint).toContain("bg-danger/");
  });

  it("falls back to neutral for a band it does not know, and for none at all", () => {
    expect(trustBandStyle(undefined)).toBe(TRUST_BAND_NEUTRAL);
    expect(trustBandStyle("")).toBe(TRUST_BAND_NEUTRAL);
    expect(trustBandStyle("Unheard Of")).toBe(TRUST_BAND_NEUTRAL);
  });

  it("keeps the failing palette colours out of the mapping entirely", () => {
    const everything = ["Safe", "Caution", "High Risk", ""]
      .map((band) => Object.values(trustBandStyle(band)).join(" "))
      .join(" ");

    expect(everything).not.toMatch(/emerald|amber|red-\d|#[0-9a-f]{6}/i);
  });
});
