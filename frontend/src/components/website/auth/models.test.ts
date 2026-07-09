/**
 * Tests for auth domain model enums (R2.7, R2.9, R2.14, R2.15).
 *
 * Ensures the frontend model enum values are in sync with the backend
 * SecurityEventType, UserPersona, and OAuthFlowMode contracts.
 * If these drift, the UI silently breaks (wrong icons, wrong redirects).
 */
import { describe, it, expect } from "vitest";
import {
  SecurityEventType,
  UserPersona,
  UserType,
  OAuthFlowMode,
  SocialProvider,
  TrustStatus,
} from "./models";

// ── SecurityEventType — R2.7 (security activity log) ─────────────────────

describe("SecurityEventType (R2.7)", () => {
  it("contains LOGIN_FAILURE_WARNING for warn-at-5 display", () => {
    expect(SecurityEventType.LOGIN_FAILURE_WARNING).toBe("LOGIN_FAILURE_WARNING");
  });

  it("contains ACCOUNT_LOCKED for lockout display", () => {
    expect(SecurityEventType.ACCOUNT_LOCKED).toBe("ACCOUNT_LOCKED");
  });

  it("contains LOGIN_SUCCESS", () => {
    expect(SecurityEventType.LOGIN_SUCCESS).toBe("LOGIN_SUCCESS");
  });

  it("contains LOGIN_FAILURE", () => {
    expect(SecurityEventType.LOGIN_FAILURE).toBe("LOGIN_FAILURE");
  });

  it("contains PASSWORD_CHANGED for reset / set-password flows", () => {
    expect(SecurityEventType.PASSWORD_CHANGED).toBe("PASSWORD_CHANGED");
  });

  it("contains PASSWORD_RESET_REQUESTED", () => {
    expect(SecurityEventType.PASSWORD_RESET_REQUESTED).toBe("PASSWORD_RESET_REQUESTED");
  });

  it("contains SESSION_REVOKED for device-management display", () => {
    expect(SecurityEventType.SESSION_REVOKED).toBe("SESSION_REVOKED");
  });

  it("contains OAUTH_LINKED and OAUTH_UNLINKED for linked-accounts display", () => {
    expect(SecurityEventType.OAUTH_LINKED).toBe("OAUTH_LINKED");
    expect(SecurityEventType.OAUTH_UNLINKED).toBe("OAUTH_UNLINKED");
  });
});

// ── UserPersona — R2.15 (persona auto-add) ────────────────────────────────

describe("UserPersona (R2.15)", () => {
  it("CUSTOMER persona exists", () => {
    expect(UserPersona.CUSTOMER).toBe("CUSTOMER");
  });

  it("AGENT persona exists", () => {
    expect(UserPersona.AGENT).toBe("AGENT");
  });
});

// ── UserType — R2.14 (post-auth redirect priority) ────────────────────────

describe("UserType (R2.14)", () => {
  it("USER type exists", () => {
    expect(UserType.USER).toBe("USER");
  });

  it("ADMIN type exists", () => {
    expect(UserType.ADMIN).toBe("ADMIN");
  });
});

// ── OAuthFlowMode — R2.9 (link / unlink) ─────────────────────────────────

describe("OAuthFlowMode (R2.9)", () => {
  it("AUTH mode is 'auth'", () => {
    expect(OAuthFlowMode.AUTH).toBe("auth");
  });

  it("LINK mode is 'link'", () => {
    expect(OAuthFlowMode.LINK).toBe("link");
  });
});

// ── SocialProvider — R2.3, R2.9 ──────────────────────────────────────────

describe("SocialProvider", () => {
  it("includes GOOGLE, APPLE, FACEBOOK", () => {
    expect(SocialProvider.GOOGLE).toBe("google");
    expect(SocialProvider.APPLE).toBe("apple");
    expect(SocialProvider.FACEBOOK).toBe("facebook");
  });
});

// ── TrustStatus ───────────────────────────────────────────────────────────

describe("TrustStatus", () => {
  it("has UNTRUSTED and TRUSTED", () => {
    expect(TrustStatus.UNTRUSTED).toBe("UNTRUSTED");
    expect(TrustStatus.TRUSTED).toBe("TRUSTED");
  });
});
