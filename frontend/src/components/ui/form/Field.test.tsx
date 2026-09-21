import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import { Field, FieldGroup } from "./Field";

/** React's generated ids are opaque, so assert the two attributes agree rather than pinning a value. */
const attr = (html: string, name: string): string | null => {
  const match = new RegExp(`${name}="([^"]+)"`).exec(html);
  return match ? match[1] : null;
};

// A label that only looks attached is invisible to assistive tech: an unbound <select> has no
// accessible name at all (axe `select-name`, critical), which is what the signup residence step
// and the OAuth profile modal both shipped before this component existed.
describe("Field", () => {
  it("binds its label to the control it wraps", () => {
    const html = renderToStaticMarkup(
      <Field label="Country of residence">{(id) => <select id={id} />}</Field>,
    );

    const boundTo = attr(html, "for");
    expect(boundTo).toBeTruthy();
    expect(attr(html, "id")).toBe(boundTo);
  });

  it("shows the error it is given", () => {
    const html = renderToStaticMarkup(
      <Field label="Timezone" error="Select your timezone">
        {(id) => <select id={id} />}
      </Field>,
    );

    expect(html).toContain("Select your timezone");
  });
});

describe("FieldGroup", () => {
  it("names the group when several controls share one label", () => {
    const html = renderToStaticMarkup(
      <FieldGroup label="Preferred currency">
        <button type="button">NGN</button>
      </FieldGroup>,
    );

    expect(html).toContain('role="group"');
    // The group is named by the label above it — there is no single control to bind to.
    expect(attr(html, "aria-labelledby")).toBe(attr(html, "id"));
  });
});
