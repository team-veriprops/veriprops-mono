import { TransactionCurrency } from "@/types/models";

export enum PayoutStatus {
  REQUESTED = "REQUESTED",
  APPROVED = "APPROVED",
  HELD = "HELD",
  PROCESSING = "PROCESSING",
  PAID = "PAID",
  FAILED = "FAILED",
  REJECTED = "REJECTED",
  CANCELLED = "CANCELLED",
}

/** A move a person can make on a payout. The backend lists the ones a payout's status allows
 * in `allowedActions`; screens offer exactly those. */
export enum PayoutAction {
  APPROVE = "APPROVE",
  HOLD = "HOLD",
  ADJUST = "ADJUST",
  REJECT = "REJECT",
  RETRY = "RETRY",
  CANCEL = "CANCEL",
}

/** A bank a payout can be sent to, from the paying gateway's own list. */
export interface Bank {
  code: string;
  name: string;
}

/** An account as the bank holds it — the name is the bank's, never typed. */
export interface ResolvedBankAccount {
  bankCode: string;
  bankName: string;
  accountNumber: string;
  accountName: string;
}

/** A stored payout beneficiary (§15.1). */
export interface BankAccount {
  id: string;
  bankName: string;
  bankCode?: string | null;
  accountNumber: string;
  accountName: string;
  isDefault: boolean;
  dateCreated: string;
}

export interface Payout {
  id: string;
  agentId: string;
  amountMinor: number;
  feeMinor: number;
  netMinor: number;
  currency: TransactionCurrency;
  status: PayoutStatus;
  bankName: string;
  accountNumber: string;
  accountName: string;
  adjustmentMinor: number;
  note?: string | null;
  requestedAt?: string | null;
  slaDueAt?: string | null;
  decidedAt?: string | null;
  settledAt?: string | null;
  dateCreated: string;
  allowedActions: PayoutAction[];
}

/** A payout as finance sees it: the transfer's trail, and the gateway's reason for a failure. */
export interface AdminPayout extends Payout {
  bankCode?: string | null;
  provider?: string | null;
  transferReference?: string | null;
  gatewayTransferId?: string | null;
  transferAttempts: number;
  sentAt?: string | null;
  failureReason?: string | null;
}

export interface RequestPayoutRequest {
  amountMinor: number;
  bankAccountId: string;
}

export interface QuotePayoutRequest {
  amountMinor: number;
  bankAccountId: string;
}

/** The transfer fee on a withdrawal, and what reaches the bank. */
export interface PayoutQuote {
  amountMinor: number;
  feeMinor: number;
  netMinor: number;
}

export interface ResolveBankAccountRequest {
  bankCode: string;
  accountNumber: string;
}

export interface AddBankAccountRequest extends ResolveBankAccountRequest {
  isDefault?: boolean;
}

export interface PayoutDecisionRequest {
  note?: string;
  adjustmentMinor?: number;
}

/** Approved payouts waiting for the next batch, the gateway balance they will draw, and the
 * transfers still with the bank (which a batch also looks up). */
export interface DisbursementQueue {
  count: number;
  totalMinor: number;
  inFlight: number;
}

/** What one disbursement run did. */
export interface DisbursementOutcome {
  paid: number;
  failed: number;
  inFlight: number;
  remaining: number;
}
