/**
 * Per-case delegate (PRD §26.4.5) — camelCase mirrors of the backend
 * `app/domain/verification/delegate` DTOs.
 *
 * The backend decides everything here. In particular `verified` is derived from a
 * timestamp server-side: never infer "this delegate can see the case" from a number being
 * present, because an authorization awaiting its OTP carries a number and grants nothing.
 */

/** The case's delegate, as the case page renders it. At most one (§26.4.5). */
export interface CaseDelegate {
  id?: string | null;
  name: string;
  phoneE164: string;
  /** Only true once they have proved control of the number. Visibility starts here. */
  verified: boolean;
  verifiedAt?: string | null;
  revokedAt?: string | null;
  revokedReason?: string | null;
}

/** The buyer nominates someone. The case comes from the route, never from this body. */
export interface AuthorizeCaseDelegate {
  name: string;
  phoneE164: string;
}

/** Where a just-sent code went, and how long before a resend is allowed. */
export interface CaseDelegateChallenge {
  phoneE164: string;
  resendAfterSeconds: number;
}
