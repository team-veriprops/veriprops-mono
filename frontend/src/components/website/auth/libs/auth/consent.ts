import { ConsentDocument, ConsentDocumentType, UserConsent } from "@components/website/auth/models";

/**
 * Which documents signup asks a new account to accept (PRD §3.2) — and only which.
 *
 * *Which versions they are is the backend's to say.* This module used to carry the versions
 * itself, and they drifted: the registry sat at 1.0.0 while the published documents moved to
 * 1.1.0, so every new account accepted a version the server did not consider current and was met
 * by the non-dismissible re-acceptance modal the moment it signed in. Nothing here may restate a
 * version again; the published list is the single source of truth.
 */
export const SIGNUP_CONSENT_TYPES: readonly ConsentDocumentType[] = Object.freeze([
  ConsentDocumentType.PLATFORM_TERMS,
  ConsentDocumentType.PRIVACY_POLICY,
]);

/**
 * The published documents signup must show, in the order it shows them. Anything the backend has
 * not published is simply absent, which is what stops the step submitting a version it never
 * displayed.
 */
export function signupConsentDocuments(published: ConsentDocument[]): ConsentDocument[] {
  return SIGNUP_CONSENT_TYPES.map((type) => published.find((doc) => doc.type === type)).filter(
    (doc): doc is ConsentDocument => !!doc,
  );
}

/** Record an acceptance against the exact version that was on screen (PRD §3.2). */
export function consentsFor(documents: ConsentDocument[], acceptedAt: string): UserConsent[] {
  return documents.map((doc) => ({
    documentType: doc.type,
    consentVersion: doc.consentVersion,
    acceptedAt,
  }));
}
