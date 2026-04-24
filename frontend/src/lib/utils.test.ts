import { describe, it, expect, vi } from "vitest";
import {
  toQueryParams,
  stringifyFilters,
  handleToggleSort,
  buildPath,
  getSearchQuery,
  getStatusBadgeColor,
  capitalizeFirst,
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

describe("handleToggleSort", () => {
  it("sets asc on a new key", () => {
    const update = vi.fn();
    handleToggleSort("name", "", update);
    expect(update).toHaveBeenCalledWith("name asc");
  });

  it("toggles asc → desc on the same key", () => {
    const update = vi.fn();
    handleToggleSort("name", "name asc", update);
    expect(update).toHaveBeenCalledWith("name desc");
  });

  it("resets to asc when switching to a different key", () => {
    const update = vi.fn();
    handleToggleSort("date", "name desc", update);
    expect(update).toHaveBeenCalledWith("date asc");
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
