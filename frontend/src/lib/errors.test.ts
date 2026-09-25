import { describe, expect, it } from "vitest";
import { HttpError } from "./FetchHttpClient";
import {
  getErrorMessage,
  isCredentialRejection,
  OFFLINE_MESSAGE,
  SERVER_ERROR_MESSAGE,
  TIMEOUT_MESSAGE,
} from "./errors";

const FALLBACK = "Could not save that preference.";
const RAW = "Exception during DB session usage: [WinError 1225] The remote computer refused the network connection";

const responseError = (httpStatus: number, message: string, reference?: string) =>
  new HttpError(message, "/things", { httpStatus, code: "X", reference });

describe("getErrorMessage", () => {
  describe("a client error (4xx)", () => {
    it("shows the backend's message, which was written for the user", () => {
      expect(getErrorMessage(responseError(409, "That email is already registered."), FALLBACK))
        .toBe("That email is already registered.");
    });

    it("falls back when the backend sent no message of its own", () => {
      // FetchHttpClient's placeholder for a body without `error.message` (e.g. FastAPI's `detail`).
      expect(getErrorMessage(responseError(422, "An error occurred"), FALLBACK)).toBe(FALLBACK);
    });
  });

  describe("a server error (5xx)", () => {
    it("never shows what the server said, even when it leaks internals", () => {
      const message = getErrorMessage(responseError(500, RAW), FALLBACK);

      expect(message).not.toContain("WinError");
      expect(message).toContain(SERVER_ERROR_MESSAGE);
    });

    it("says it is on our side rather than using the caller's fallback, which may blame the user", () => {
      // The login form's fallback is "Email or password is incorrect." — wrong during an outage.
      expect(getErrorMessage(responseError(503, RAW), "Email or password is incorrect."))
        .not.toContain("incorrect");
    });

    it("appends the reference so support can find the failure in the logs", () => {
      expect(getErrorMessage(responseError(500, RAW, "7F3K92QA"), FALLBACK))
        .toBe(`${SERVER_ERROR_MESSAGE} Ref: 7F3K92QA`);
    });

    it("applies to every 5xx, including a gateway failure", () => {
      expect(getErrorMessage(responseError(502, "AWS SES error (Throttling): AKIA…"), FALLBACK))
        .toBe(SERVER_ERROR_MESSAGE);
    });
  });

  it("explains a request that never reached the server", () => {
    expect(getErrorMessage(new HttpError("Network error", "/things", { kind: "network" }), FALLBACK))
      .toBe(OFFLINE_MESSAGE);
  });

  it("explains a request that timed out", () => {
    expect(getErrorMessage(new HttpError("Request aborted", "/things", { kind: "timeout" }), FALLBACK))
      .toBe(TIMEOUT_MESSAGE);
  });

  it("never shows a runtime error's text", () => {
    expect(getErrorMessage(new TypeError("Cannot read properties of undefined (reading 'id')"), FALLBACK))
      .toBe(FALLBACK);
  });

  it("copes with something that is not an Error at all", () => {
    expect(getErrorMessage("boom", FALLBACK)).toBe(FALLBACK);
    expect(getErrorMessage(undefined, FALLBACK)).toBe(FALLBACK);
  });

  it("has a default fallback for callers that give none", () => {
    expect(getErrorMessage(new Error("x"))).toBeTruthy();
  });
});

describe("isCredentialRejection", () => {
  it("is true only when the backend rejected the credentials", () => {
    expect(isCredentialRejection(responseError(401, "Invalid username or password"))).toBe(true);
  });

  it("is false for a server failure or a lost connection — neither is the user's doing", () => {
    expect(isCredentialRejection(responseError(500, RAW))).toBe(false);
    expect(isCredentialRejection(new HttpError("Network error", "/x", { kind: "network" }))).toBe(false);
    expect(isCredentialRejection(new Error("x"))).toBe(false);
  });
});
