import { ConsentDocument, ConsentDocumentType } from "@components/website/auth/models";
/**
 * Versioned consent registry. Every legal document the user must accept
 * is keyed by `type` and `version`. PRD §3.2: every acceptance is recorded
 * against the exact version shown.
 *
 * To bump a version:
 *   1. Add a new entry below with a higher semver and later effectiveAt.
 *   2. Existing accepted users will be prompted to re-accept on next relevant action
 *      (handled by the backend; UI surfaces a non-dismissible modal — Phase 2.x).
 */

const documents: ConsentDocument[] = [
  {
    type: ConsentDocumentType.PLATFORM_TERMS,
    consentVersion: "1.0.0",
    effectiveAt: "2026-01-15",
    title: "Platform Terms of Service",
    href: "/legal/terms",
  },
  {
    type: ConsentDocumentType.PRIVACY_POLICY,
    consentVersion: "1.0.0",
    effectiveAt: "2026-01-15",
    title: "Privacy Policy",
    href: "/legal/privacy",
  },
  {
    type: ConsentDocumentType.AGENT_TERMS,
    consentVersion: "1.0.0",
    effectiveAt: "2026-01-15",
    title: "Agent Terms",
    href: "/legal/agent-terms",
  },
  {
    type: ConsentDocumentType.VERIFICATION_TERMS,
    consentVersion: "1.0.0",
    effectiveAt: "2026-01-15",
    title: "Verification Terms",
    href: "/legal/verification-terms",
  },
  {
    type: ConsentDocumentType.REPORT_DISCLAIMER,
    consentVersion: "1.0.0",
    effectiveAt: "2026-01-15",
    title: "Report Disclaimer",
    href: "/legal/report-disclaimer",
  },
];

export const CONSENT_REGISTRY: ReadonlyArray<ConsentDocument> = Object.freeze(documents);

export const getCurrentConsent = (type: ConsentDocumentType): ConsentDocument => {
  // Pick the latest version per type by effectiveAt.
  const byType = CONSENT_REGISTRY.filter((d) => d.type === type);
  if (byType.length === 0) {
    throw new Error(`No consent document registered for type: ${type}`);
  }
  return byType.reduce((acc, cur) =>
    new Date(cur.effectiveAt).getTime() > new Date(acc.effectiveAt).getTime() ? cur : acc,
  );
};

/**
 * The two consent docs presented at signup (PRD §3.2).
 */
export const SIGNUP_CONSENT_DOCUMENTS: ConsentDocument[] = [
  getCurrentConsent(ConsentDocumentType.PLATFORM_TERMS),
  getCurrentConsent(ConsentDocumentType.PRIVACY_POLICY),
];
