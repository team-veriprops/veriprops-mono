import { describe, expect, it } from "vitest";
import { ConsentDocument, ConsentDocumentType } from "@components/website/auth/models";

import { consentsFor, signupConsentDocuments, SIGNUP_CONSENT_TYPES } from "./consent";

/** The published list as the backend serves it — Platform Terms and Privacy at 1.1.0. */
const published: ConsentDocument[] = [
  {
    type: ConsentDocumentType.PLATFORM_TERMS,
    consentVersion: "1.1.0",
    effectiveAt: "2026-09-03T00:00:00Z",
    title: "Platform Terms of Service",
    href: "/legal/terms",
  },
  {
    type: ConsentDocumentType.PRIVACY_POLICY,
    consentVersion: "1.1.0",
    effectiveAt: "2026-09-03T00:00:00Z",
    title: "Privacy Policy",
    href: "/legal/privacy",
  },
  {
    type: ConsentDocumentType.AGENT_TERMS,
    consentVersion: "1.0.0",
    effectiveAt: "2026-01-15T00:00:00Z",
    title: "Agent Terms",
    href: "/legal/agent-terms",
  },
];

describe("signupConsentDocuments", () => {
  it("picks the two documents signup asks for, in the order it shows them", () => {
    const documents = signupConsentDocuments(published);

    expect(documents.map((d) => d.type)).toEqual([...SIGNUP_CONSENT_TYPES]);
  });

  it("takes the version from the published list rather than from anything local", () => {
    const [terms, privacy] = signupConsentDocuments(published);

    expect(terms.consentVersion).toBe("1.1.0");
    expect(privacy.consentVersion).toBe("1.1.0");
  });

  it("leaves out a document the backend has not published", () => {
    const documents = signupConsentDocuments([published[0]]);

    expect(documents.map((d) => d.type)).toEqual([ConsentDocumentType.PLATFORM_TERMS]);
  });
});

describe("consentsFor", () => {
  it("records each acceptance against the exact version shown", () => {
    const acceptedAt = "2026-09-22T10:00:00.000Z";

    expect(consentsFor(signupConsentDocuments(published), acceptedAt)).toEqual([
      {
        documentType: ConsentDocumentType.PLATFORM_TERMS,
        consentVersion: "1.1.0",
        acceptedAt,
      },
      { documentType: ConsentDocumentType.PRIVACY_POLICY, consentVersion: "1.1.0", acceptedAt },
    ]);
  });
});

/**
 * The defect this module was rewritten for: a hardcoded version here sat at 1.0.0 while the
 * backend published 1.1.0, so every new account was immediately blocked by the re-acceptance
 * modal. Handing back the published document itself — rather than a local copy of it — is what
 * makes a stale version impossible to reintroduce.
 */
describe("the published document is what signup uses", () => {
  it("hands back the backend's own documents, not local substitutes", () => {
    const documents = signupConsentDocuments(published);

    expect(documents[0]).toBe(published[0]);
    expect(documents[1]).toBe(published[1]);
  });
});
