import { describe, it, expect } from "vitest";
import {
  toQueryParams,
  stringifyFilters,
  nextOrderBy,
  buildPath,
  getSearchQuery,
  getStatusBadgeColor,
  capitalizeFirst,
  humanizeEnumLabel,
} from "./utils";

describe("toQueryParams", () => {
  it("serializes primitive values", () => {
    expect(toQueryParams({ page: 1, search: "test" })).toBe(
      "page=1&search=test"
    );
  });

  it("omits null and undefined values", () => {
    expect(toQueryParams({ a: null, b: undefined, c: "keep" })).toBe("c=keep");
  });

  it("appends array values as repeated keys", () => {
    const result = toQueryParams({ ids: [1, 2, 3] });
    expect(result).toBe("ids=1&ids=2&ids=3");
  });

  it("stringifies nested objects", () => {
    const result = toQueryParams({ filter: { min: 1, max: 10 } });
    expect(result).toBe('filter=%7B%22min%22%3A1%2C%22max%22%3A10%7D');
  });
});

describe("stringifyFilters", () => {
  it("converts primitive values to strings", () => {
    expect(stringifyFilters({ page: 1, active: true })).toEqual({
      page: "1",
      active: "true",
    });
  });

  it("JSON-stringifies object values", () => {
    expect(stringifyFilters({ range: { min: 0, max: 5 } })).toEqual({
      range: '{"min":0,"max":5}',
    });
  });
});

describe("nextOrderBy", () => {
  it("starts ascending with no sort in force", () => {
    expect(nextOrderBy(undefined, "name")).toBe("name asc");
    expect(nextOrderBy("", "name")).toBe("name asc");
  });

  it("flips the same column asc ↔ desc", () => {
    expect(nextOrderBy("name asc", "name")).toBe("name desc");
    expect(nextOrderBy("name desc", "name")).toBe("name asc");
  });

  it("starts another column ascending", () => {
    expect(nextOrderBy("name desc", "date")).toBe("date asc");
  });
});

describe("buildPath", () => {
  it("replaces template placeholders with params", () => {
    expect(buildPath("/users/{id}/posts/{postId}", { id: "42", postId: "7" })).toBe(
      "/users/42/posts/7"
    );
  });

  it("leaves unmatched placeholders empty", () => {
    expect(buildPath("/users/{id}", {})).toBe("/users/");
  });
});

describe("getSearchQuery", () => {
  it("returns the lowercase value for a known key", () => {
    expect(getSearchQuery("q", "q=Hello%20World")).toBe("hello world");
  });

  it("returns empty string when key is absent", () => {
    expect(getSearchQuery("q", "page=1")).toBe("");
  });
});

describe("getStatusBadgeColor", () => {
  it("returns correct class for known statuses", () => {
    expect(getStatusBadgeColor("pending")).toContain("bg-muted");
    expect(getStatusBadgeColor("completed")).toContain("bg-success");
    expect(getStatusBadgeColor("flagged")).toContain("bg-danger");
  });

  it("falls back to muted for unknown status", () => {
    expect(getStatusBadgeColor("unknown_status")).toContain("bg-muted");
  });
});

describe("capitalizeFirst", () => {
  it("capitalizes the first letter", () => {
    expect(capitalizeFirst("hello")).toBe("Hello");
  });

  it("handles already capitalized strings", () => {
    expect(capitalizeFirst("Hello")).toBe("Hello");
  });
});

describe("humanizeEnumLabel", () => {
  it("title-cases a SCREAMING_SNAKE_CASE enum", () => {
    expect(humanizeEnumLabel("UNDER_REVIEW")).toBe("Under Review");
    expect(humanizeEnumLabel("PAYMENT_PENDING")).toBe("Payment Pending");
    expect(humanizeEnumLabel("PENDING")).toBe("Pending");
  });

  it("returns an empty string for nullish input", () => {
    expect(humanizeEnumLabel(null)).toBe("");
    expect(humanizeEnumLabel(undefined)).toBe("");
    expect(humanizeEnumLabel("")).toBe("");
  });
});
