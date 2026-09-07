/**
 * WhatsApp messaging consent (PRD §26.4.6) — camelCase mirrors of the backend
 * `app/domain/channel/whatsapp/consent` DTOs.
 *
 * The backend derives `utility` / `marketing` from a grant/revoke timestamp pair, so these
 * are read-only facts here: never recompute them on the client, and never treat "no record
 * yet" as anything but both off. §26.4.6 requires both controls to start unticked.
 */

/** The two §26.4.6 opt-ins, as any consent surface renders them. */
export interface WhatsAppConsent {
  /** "Send me progress updates about this verification on WhatsApp." */
  utility: boolean;
  /** "Send me occasional Veriprops news and offers on WhatsApp." */
  marketing: boolean;
  utilityUpdatedAt?: string | null;
  marketingUpdatedAt?: string | null;
}

/** Both controls are always submitted together — see the backend DTO for why. */
export interface SetWhatsAppConsent {
  utility: boolean;
  marketing: boolean;
}

/**
 * Where a consent decision was made. Only the two authenticated surfaces are selectable
 * from the browser; `WA_PAY_LANDING` is set by the grant-scoped endpoint and the two
 * keyword sources are recorded by the bot.
 */
export enum WhatsAppConsentSource {
  PAY_SCREEN = "PAY_SCREEN",
  ACCOUNT_SETTINGS = "ACCOUNT_SETTINGS",
}

/** Both unticked — the state a customer who has never been asked is in. */
export const NO_WHATSAPP_CONSENT: WhatsAppConsent = { utility: false, marketing: false };
