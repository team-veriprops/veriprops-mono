import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import PhoneInputWithCountry from "./PhoneInputWithCountry";

function render(props: { disabled?: boolean; isVerified?: boolean }) {
  return renderToStaticMarkup(
    <PhoneInputWithCountry
      countryCode="NG"
      phone="8012345678"
      onChange={vi.fn()}
      placeholder="Phone number"
      data-testid="phone"
      {...props}
    />,
  );
}

// A container dimmed with `opacity-50` drags the dial-code text below the 4.5:1 contrast minimum
// (axe `color-contrast`). Disabled controls — the input, the country button — are exempt from
// the rule; the dial code beside them is not, so the check is anchored on that text.
const DIMMED_CONTAINER_WRAPPING_TEXT = /class="[^"]*\bopacity-50\b[^"]*"[^>]*>\s*<span[^>]*>\+234</;

describe("PhoneInputWithCountry", () => {
  it("keeps the dial code readable while the number is locked for a pending code", () => {
    const html = render({ disabled: true });

    expect(html).toContain("+234");
    expect(html).not.toMatch(DIMMED_CONTAINER_WRAPPING_TEXT);
    expect(html).toMatch(/<input[^>]*disabled/);
  });

  it("keeps the dial code readable once the number is verified", () => {
    const html = render({ isVerified: true });

    expect(html).not.toMatch(DIMMED_CONTAINER_WRAPPING_TEXT);
  });
});
