import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import { SubmitButton } from "./SubmitButton";

/**
 * `renderToStaticMarkup` is exactly the HTML a browser can act on before React hydrates. A
 * submit button that is already live at that point submits its form natively, which appends
 * every field — on an auth form, the password — to the URL.
 */
describe("SubmitButton", () => {
  it("is disabled in the markup the server sends", () => {
    const html = renderToStaticMarkup(<SubmitButton>Save password</SubmitButton>);

    expect(html).toContain('type="submit"');
    expect(html).toContain("disabled");
  });

  it("stays disabled while the form is busy", () => {
    const html = renderToStaticMarkup(<SubmitButton disabled>Saving…</SubmitButton>);

    expect(html).toContain("disabled");
  });
});
