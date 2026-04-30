import { describe, it, expect } from "vitest";
import {
  CONSENT_REGISTRY,
  getCurrentConsent,
  SIGNUP_CONSENT_DOCUMENTS,
} from "./consent";
import { ConsentDocumentType } from "@components/website/auth/models";
describe("CONSENT_REGISTRY", () => {
  it("is frozen (immutable)", () => {
    expect(Object.isFrozen(CONSENT_REGISTRY)).toBe(true);
  });

  it("covers all required document types from PRD §3.2", () => {
    const types = new Set(CONSENT_REGISTRY.map((d) => d.type));
    expect(types.has(ConsentDocumentType.PLATFORM_TERMS)).toBe(true);
    expect(types.has(ConsentDocumentType.PRIVACY_POLICY)).toBe(true);
    expect(types.has(ConsentDocumentType.AGENT_TERMS)).toBe(true);
    expect(types.has(ConsentDocumentType.VERIFICATION_TERMS)).toBe(true);
    expect(types.has(ConsentDocumentType.REPORT_DISCLAIMER)).toBe(true);
  });

  it("every entry has a semver-style version", () => {
    for (const doc of CONSENT_REGISTRY) {
      expect(doc.consentVersion).toMatch(/^\d+\.\d+\.\d+$/);
    }
  });

  it("every entry has a valid effectiveAt date", () => {
    for (const doc of CONSENT_REGISTRY) {
      expect(Number.isFinite(new Date(doc.effectiveAt).getTime())).toBe(true);
    }
  });
});

describe("getCurrentConsent", () => {
  it("returns the latest version per type", () => {
    const platform = getCurrentConsent(ConsentDocumentType.PLATFORM_TERMS);
    expect(platform.type).toBe(ConsentDocumentType.PLATFORM_TERMS);
    expect(platform.consentVersion).toBeTruthy();
  });
});

describe("SIGNUP_CONSENT_DOCUMENTS", () => {
  it("includes platform terms and privacy policy", () => {
    const types = SIGNUP_CONSENT_DOCUMENTS.map((d) => d.type);
    expect(types).toContain(ConsentDocumentType.PLATFORM_TERMS);
    expect(types).toContain(ConsentDocumentType.PRIVACY_POLICY);
  });

  it("does not include verification or report consents (those are gated later)", () => {
    const types = SIGNUP_CONSENT_DOCUMENTS.map((d) => d.type);
    expect(types).not.toContain(ConsentDocumentType.VERIFICATION_TERMS);
    expect(types).not.toContain(ConsentDocumentType.REPORT_DISCLAIMER);
  });
});
