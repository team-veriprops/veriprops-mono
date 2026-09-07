/**
 * WhatsApp account-linking types (PRD §26.4.4) — camelCase mirrors of the backend
 * `app/domain/channel/whatsapp/link` DTOs.
 *
 * Backend owns every fact here. The page renders the status it is given; it never infers
 * whether a number is linked from the presence of a string, because a number can be
 * present on a *pending* row that grants nothing.
 */

export enum WhatsAppLinkStatus {
  PENDING = "PENDING",
  ACTIVE = "ACTIVE",
  REVOKED = "REVOKED",
}

/** The account's link, as the settings page renders it. */
export interface WhatsAppLink {
  phoneE164?: string | null;
  status: WhatsAppLinkStatus;
  linkedAt?: string | null;
}

/** Where a just-sent linking code went, and how long before a resend is allowed. */
export interface WhatsAppLinkChallenge {
  phoneE164: string;
  resendAfterSeconds: number;
}
