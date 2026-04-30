import { describe, it, expect } from "vitest";
import { ROUTES, isAuthIntent, buildAuthUrl } from "./routes";

describe("ROUTES", () => {
  it("exposes auth gate, login, signup, forgot/reset, oauth callback", () => {
    expect(ROUTES.AUTH.GATE).toBe("/auth");
    expect(ROUTES.AUTH.LOGIN).toBe("/auth/login");
    expect(ROUTES.AUTH.SIGNUP).toBe("/auth/signup");
    expect(ROUTES.AUTH.FORGOT_PASSWORD).toBe("/auth/forgot-password");
    expect(ROUTES.AUTH.SET_PASSWORD).toBe("/auth/set-password");
    expect(ROUTES.AUTH.RESET_PASSWORD("abc")).toBe("/auth/reset-password/abc");
    expect(ROUTES.AUTH.OAUTH_CALLBACK("google")).toBe("/auth/oauth/google/callback");
  });

  it("exposes account routes", () => {
    expect(ROUTES.ACCOUNT.SECURITY).toBe("/account/security");
    expect(ROUTES.ACCOUNT.DEVICES).toBe("/account/devices");
    expect(ROUTES.ACCOUNT.LINKED).toBe("/account/linked");
  });
});

describe("isAuthIntent", () => {
  it("accepts the 3 known intents", () => {
    expect(isAuthIntent("verify")).toBe(true);
    expect(isAuthIntent("agent")).toBe(true);
    expect(isAuthIntent("default")).toBe(true);
  });

  it("rejects everything else", () => {
    expect(isAuthIntent(null)).toBe(false);
    expect(isAuthIntent(undefined)).toBe(false);
    expect(isAuthIntent("")).toBe(false);
    expect(isAuthIntent("anything")).toBe(false);
  });
});

describe("buildAuthUrl", () => {
  it("returns the base when no params provided", () => {
    expect(buildAuthUrl("/auth/login")).toBe("/auth/login");
  });

  it("omits intent=default", () => {
    expect(buildAuthUrl("/auth/login", { intent: "default" })).toBe("/auth/login");
  });

  it("preserves intent + tier + redirect", () => {
    const url = buildAuthUrl("/auth/signup", {
      intent: "verify",
      tier: "standard",
      redirect: "/portal/verifications/abc",
    });
    expect(url).toContain("intent=verify");
    expect(url).toContain("tier=standard");
    expect(url).toContain("redirect=%2Fportal%2Fverifications%2Fabc");
  });
});
