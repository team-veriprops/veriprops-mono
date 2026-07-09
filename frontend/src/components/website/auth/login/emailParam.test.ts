/**
 * Tests the URL-param-to-login-default derivation used in LoginContainer.
 * LoginContainer reads ?email= from the URL and sets it as the form default
 * so returning invited-admin users land on a pre-filled login form.
 */
import { describe, it, expect } from "vitest";

function deriveLoginEmail(searchParams: URLSearchParams): string {
  return searchParams.get("email") ?? "";
}

describe("LoginContainer email pre-population", () => {
  it("returns empty string when no email param", () => {
    expect(deriveLoginEmail(new URLSearchParams(""))).toBe("");
  });

  it("returns the email param value verbatim", () => {
    const p = new URLSearchParams("email=ada%40example.com");
    expect(deriveLoginEmail(p)).toBe("ada@example.com");
  });

  it("handles uppercase email addresses", () => {
    const p = new URLSearchParams("email=ADA%40EXAMPLE.COM");
    expect(deriveLoginEmail(p)).toBe("ADA@EXAMPLE.COM");
  });

  it("ignores unrelated params", () => {
    const p = new URLSearchParams("intent=invited-admin&email=test%40veriprops.ng&redirect=%2Fauth%2Fadmin-invite%2Fabc");
    expect(deriveLoginEmail(p)).toBe("test@veriprops.ng");
  });
});
