import { describe, it, expect } from "vitest";
import {
  RESIDENCE_COUNTRIES,
  COMMON_TIMEZONES,
  SUPPORTED_CURRENCIES,
  findCountry,
  suggestTimezoneForCountry,
} from "./locale";
import { TransactionCurrency } from "@/types/models";

describe("RESIDENCE_COUNTRIES", () => {
  it("includes Nigeria (the home market)", () => {
    expect(findCountry("NG")?.name).toBe("Nigeria");
    expect(findCountry("NG")?.defaultCurrency).toBe(TransactionCurrency.NGN);
  });

  it("includes the major diaspora origins", () => {
    const codes = RESIDENCE_COUNTRIES.map((c) => c.code);
    expect(codes).toContain("GB");
    expect(codes).toContain("US");
    expect(codes).toContain("CA");
    expect(codes).toContain("DE");
  });

  it("every country has a flag emoji", () => {
    for (const c of RESIDENCE_COUNTRIES) {
      expect(c.flag.length).toBeGreaterThan(0);
    }
  });

  it("every country has a sensible default IANA timezone", () => {
    for (const c of RESIDENCE_COUNTRIES) {
      expect(c.defaultTimezone).toMatch(/^[A-Za-z_]+\/[A-Za-z_]+$/);
    }
  });
});

describe("COMMON_TIMEZONES", () => {
  it("includes UTC", () => {
    expect(COMMON_TIMEZONES).toContain("UTC");
  });

  it("contains all country defaults", () => {
    for (const c of RESIDENCE_COUNTRIES) {
      expect(COMMON_TIMEZONES).toContain(c.defaultTimezone);
    }
  });
});

describe("SUPPORTED_CURRENCIES", () => {
  it("matches PRD currency list", () => {
    expect(SUPPORTED_CURRENCIES).toEqual([
      TransactionCurrency.NGN,
      TransactionCurrency.USD,
      TransactionCurrency.GBP,
      TransactionCurrency.EUR,
    ]);
  });
});

describe("suggestTimezoneForCountry", () => {
  it("returns the country's default when browser tz is missing", () => {
    expect(suggestTimezoneForCountry("NG")).toBe("Africa/Lagos");
  });

  it("respects browser tz when continents match", () => {
    expect(suggestTimezoneForCountry("US", "America/Los_Angeles")).toBe(
      "America/Los_Angeles",
    );
  });

  it("falls back to country default when continents differ", () => {
    expect(suggestTimezoneForCountry("US", "Africa/Lagos")).toBe("America/New_York");
  });

  it("falls back gracefully for unknown country codes", () => {
    expect(suggestTimezoneForCountry("ZZ")).toBeTruthy();
  });
});
