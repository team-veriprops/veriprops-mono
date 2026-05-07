// ─────────────────────────────────────────────────────────────────────────────
// domains/[DOMAIN_NAME]/selectors.ts
// [CLAUDE: Map every UI element this domain interacts with to a selector key.]
// [CLAUDE: Keys are referenced in journeys.ts steps — never put raw selectors
//          in journey steps. Always add the selector here first.]
// [CLAUDE: Use data-testid attributes where available — they survive UI refactors.]
// [CLAUDE: Prefer CSS selectors over XPath. Use text selectors sparingly.]
// [CLAUDE: Group selectors by page or feature section using comment blocks.]
// ─────────────────────────────────────────────────────────────────────────────

import type { SelectorMap } from "../../core/types.js";

// [CLAUDE: Add one entry per interactive element. Examples below show the pattern.]
// [CLAUDE: Keys should be camelCase and self-documenting.]
// [CLAUDE: If the domain has no browser journeys, export an empty object.]

export const selectors: SelectorMap = {
  // ── [Page or section name] ────────────────────────────────────────────────
  // [CLAUDE: Group related selectors under a comment block per page/section.]

  // [CLAUDE: Example — replace with real selectors for this domain:]
  // submitButton: "[data-testid='submit-btn']",
  // emailInput:   "[data-testid='email-input']",
  // errorBanner:  "[data-testid='error-banner']",
  // successToast: "[data-testid='success-toast']",
  // navLink:      "nav a[href='/[route]']",
};
