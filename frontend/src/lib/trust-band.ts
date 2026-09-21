/**
 * How a trust band is presented, in one place (PRD §10.1, §13.1).
 *
 * The band is the report's headline verdict, and it appears on two surfaces that must agree:
 * the owner's report and the public share card (§10.2 parity). Stating the mapping once keeps
 * them from drifting — and keeps the colours honest. The palette shades this replaced failed
 * WCAG AA against the panel behind them (3.50:1 Safe, 2.83:1 Caution, 4.48:1 High Risk, where
 * AA needs 4.5:1), so the mapping is expressed in the theme's semantic tokens, which are
 * chosen for contrast and carry their own dark-mode values.
 */

export interface TrustBandStyle {
  /** Colours the band label. */
  text: string;
  /** Colours the gauge arc — a class, not a hex, so the arc follows the theme. */
  stroke: string;
  /** Softly fills the panel the score sits in. */
  tint: string;
}

/** The bands the backend issues. It owns the verdict; this only dresses it. */
const TRUST_BAND_STYLES: Record<string, TrustBandStyle> = {
  Safe: {
    text: "text-success",
    stroke: "stroke-success",
    tint: "bg-success/5 border-success/20",
  },
  Caution: {
    text: "text-warning",
    stroke: "stroke-warning",
    tint: "bg-warning/5 border-warning/20",
  },
  "High Risk": {
    text: "text-danger",
    stroke: "stroke-danger",
    tint: "bg-danger/5 border-danger/20",
  },
};

/** Used before a score exists, and for any band this build does not recognise. */
export const TRUST_BAND_NEUTRAL: TrustBandStyle = {
  text: "text-muted-foreground",
  stroke: "stroke-muted-foreground",
  tint: "",
};

/** The presentation for *band*, falling back to neutral rather than to an unstyled label. */
export function trustBandStyle(band?: string | null): TrustBandStyle {
  return (band && TRUST_BAND_STYLES[band]) || TRUST_BAND_NEUTRAL;
}
