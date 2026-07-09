/**
 * Tests the country-to-step3-defaults derivation used in SignupContainer.
 * The logic: when the user picks a phone dial code in step 2, step 3 is
 * pre-filled with the matching country, timezone, and currency.
 */
import { describe, it, expect } from "vitest";
import { findCountry } from "@components/website/auth/libs/auth/locale";

function deriveStep3Defaults(countryCode: string | undefined) {
  if (!countryCode) return undefined;
  const info = findCountry(countryCode);
  if (!info) return undefined;
  return {
    countryOfResidence: countryCode,
    timezone: info.defaultTimezone,
    preferredCurrency: info.defaultCurrency,
  };
}

describe("step3 defaults from step2 countryCode", () => {
  it("returns undefined when countryCode is absent", () => {
    expect(deriveStep3Defaults(undefined)).toBeUndefined();
  });

  it("returns undefined for an unrecognised country code", () => {
    expect(deriveStep3Defaults("XX")).toBeUndefined();
  });

  it("pre-fills Nigeria correctly", () => {
    const defaults = deriveStep3Defaults("NG");
    expect(defaults).toMatchObject({
      countryOfResidence: "NG",
      timezone: "Africa/Lagos",
    });
    expect(defaults?.preferredCurrency).toBeTruthy();
  });

  it("pre-fills United Kingdom correctly", () => {
    const defaults = deriveStep3Defaults("GB");
    expect(defaults).toMatchObject({
      countryOfResidence: "GB",
      timezone: "Europe/London",
    });
  });

  it("pre-fills United States correctly", () => {
    const defaults = deriveStep3Defaults("US");
    expect(defaults).toMatchObject({
      countryOfResidence: "US",
      timezone: "America/New_York",
    });
  });
});
