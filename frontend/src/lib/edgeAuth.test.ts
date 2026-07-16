import { describe, expect, it } from "vitest";

import { EDGE_AUTH_HEADER, isEdgeAuthorized } from "./edgeAuth";

const SECRET = "test-edge-secret-value";

describe("isEdgeAuthorized", () => {
  describe("disabled (no secret configured)", () => {
    it("allows requests when the secret is undefined", () => {
      expect(isEdgeAuthorized(null, undefined)).toBe(true);
    });

    it("allows requests when the secret is empty", () => {
      expect(isEdgeAuthorized(null, "")).toBe(true);
    });

    it("allows requests when the secret is whitespace", () => {
      expect(isEdgeAuthorized(null, "   ")).toBe(true);
    });

    it("allows requests when the secret is the CHANGE_ME placeholder", () => {
      expect(isEdgeAuthorized(null, "CHANGE_ME")).toBe(true);
    });
  });

  describe("enforced (secret configured)", () => {
    it("rejects a missing header", () => {
      expect(isEdgeAuthorized(null, SECRET)).toBe(false);
    });

    it("rejects an empty header", () => {
      expect(isEdgeAuthorized("", SECRET)).toBe(false);
    });

    it("rejects a wrong header value", () => {
      expect(isEdgeAuthorized("wrong-value", SECRET)).toBe(false);
    });

    it("rejects a value of different length", () => {
      expect(isEdgeAuthorized(`${SECRET}x`, SECRET)).toBe(false);
    });

    it("accepts the correct header value", () => {
      expect(isEdgeAuthorized(SECRET, SECRET)).toBe(true);
    });
  });
});

describe("EDGE_AUTH_HEADER", () => {
  it("matches the backend's default header name", () => {
    expect(EDGE_AUTH_HEADER).toBe("x-edge-auth");
  });
});
