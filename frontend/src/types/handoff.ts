/**
 * WhatsApp handoff types (PRD §26.4.2, §26.5) — camelCase mirrors of the backend
 * `app/domain/channel/whatsapp/handoff` DTOs.
 *
 * A handoff link authorizes exactly one action on one case for fifteen minutes. Backend
 * owns every decision about it; the landing pages render what redemption returns and
 * never infer validity themselves.
 */
import { TransactionCurrency } from "./models";
import { VerificationStatus, VerificationTier } from "./verification";

export enum HandoffIntent {
  PAY = "pay",
  UPLOAD = "upload",
  REPORT = "report",
}

/** What a landing page acknowledges: "picking up where you left off" (§26.4.2). */
export interface HandoffContext {
  intent: HandoffIntent;
  caseId: string;
  /** The opaque short code (VP-1042) — never the address or customer name (§26.4.3). */
  vid: string;
  tier: VerificationTier;
  status: VerificationStatus;
  amountDueMinor?: number | null;
  currency?: TransactionCurrency | null;
  expiresAt: string;
}

/** The checkout a redeemed `pay` link opens. */
export interface HandoffPayment {
  txRef: string;
  checkoutUrl?: string | null;
  amountMinor: number;
  currency: TransactionCurrency;
}


/** Where a redeemed chat-intake link sends the customer (§5.1, D69). */
export interface SeededDraft {
  verificationId: string;
}
