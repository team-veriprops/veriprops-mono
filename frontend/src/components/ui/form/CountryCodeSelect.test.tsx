import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import CountryCodeSelect from "./CountryCodeSelect";

// The trigger shows only a flag emoji, so without an explicit label a screen reader announces an
// unnamed combobox — axe's critical `button-name` rule on every phone form that uses it.
describe("CountryCodeSelect", () => {
  it("names its trigger by the selected country and dial code", () => {
    const html = renderToStaticMarkup(<CountryCodeSelect value="NG" onChange={vi.fn()} />);

    expect(html).toContain('aria-label="Country code: Nigeria +234"');
  });

  it("still names its trigger when no country is selected", () => {
    const html = renderToStaticMarkup(<CountryCodeSelect value="" onChange={vi.fn()} />);

    expect(html).toContain('aria-label="Country code"');
  });
});
