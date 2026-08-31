import { describe, it, expect } from "vitest";
import { PAYMENT_FLOW_PATH_PATTERNS, ROUTES, isAuthIntent, buildAuthUrl } from "./routes";
import { AuthIntent } from "@/components/website/auth/models";

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

  it(`omits intent=${AuthIntent.DEFAULT}`, () => {
    expect(buildAuthUrl("/auth/login", { intent: AuthIntent.DEFAULT })).toBe("/auth/login");
  });

  it("preserves intent + tier + redirect", () => {
    const url = buildAuthUrl("/auth/signup", {
      intent: AuthIntent.VERIFY,
      tier: "standard",
      redirect: "/portal/verifications/abc",
    });
    expect(url).toContain(`intent=${AuthIntent.VERIFY}`);
    expect(url).toContain("tier=standard");
    expect(url).toContain("redirect=%2Fportal%2Fverifications%2Fabc");
  });

  it("carries signup prefill params (email, firstName, lastName), URL-encoded", () => {
    const url = buildAuthUrl("/auth/signup", {
      intent: AuthIntent.INVITED_ADMIN,
      email: "ada+admin@example.com",
      firstName: "Ada",
      lastName: "Lovelace Byron",
    });
    expect(url).toContain("email=ada%2Badmin%40example.com");
    expect(url).toContain("firstName=Ada");
    expect(url).toContain("lastName=Lovelace+Byron");
  });

  it("omits prefill params that are absent or empty", () => {
    const url = buildAuthUrl("/auth/signup", {
      email: "ada@example.com",
      firstName: null,
      lastName: "",
    });
    expect(url).toBe("/auth/signup?email=ada%40example.com");
  });
});

describe("WhatsApp handoff routes", () => {
  it("builds the three token landings", () => {
    expect(ROUTES.WA.PAY("tok")).toBe("/wa/pay/tok");
    expect(ROUTES.WA.UPLOAD("tok")).toBe("/wa/upload/tok");
    expect(ROUTES.WA.REPORT("tok")).toBe("/wa/report/tok");
  });

  it("keeps the landings outside every protected surface", () => {
    // The handoff token is the authorization (§7.5) — a customer arriving from WhatsApp
    // must not be bounced to a login page before the landing can even acknowledge their
    // case. proxy.ts derives its protected prefixes from these constants.
    const protectedPrefixes = [
      ROUTES.PORTAL.GATE,
      ROUTES.ADMIN.GATE,
      ROUTES.AGENT.GATE,
      ROUTES.ACCOUNT.ROOT,
    ];
    for (const landing of [ROUTES.WA.PAY("t"), ROUTES.WA.UPLOAD("t"), ROUTES.WA.REPORT("t")]) {
      expect(protectedPrefixes.some((p) => landing.startsWith(p))).toBe(false);
    }
  });
});

describe("PAYMENT_FLOW_PATH_PATTERNS", () => {
  it("matches what the pay route builders produce", () => {
    // The patterns mirror the builders; if one moves without the other, the widget stops
    // suppressing itself at the payment step.
    const matches = (path: string) => PAYMENT_FLOW_PATH_PATTERNS.some((p) => p.test(path));
    expect(matches(ROUTES.PORTAL.VERIFICATION_PAY("abc"))).toBe(true);
    expect(matches(ROUTES.WA.PAY("tok"))).toBe(true);
  });
});
