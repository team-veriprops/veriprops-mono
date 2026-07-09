import { TransactionCurrency } from "@/types/models";

export enum PayoutStatus {
  REQUESTED = "REQUESTED",
  APPROVED = "APPROVED",
  HELD = "HELD",
  PAID = "PAID",
  REJECTED = "REJECTED",
  CANCELLED = "CANCELLED",
}

/** A stored payout beneficiary (§15.1). */
export interface BankAccount {
  id: string;
  bankName: string;
  accountNumber: string;
  accountName: string;
  isDefault: boolean;
  dateCreated: string;
}

export interface Payout {
  id: string;
  agentId: string;
  amountMinor: number;
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
  dateCreated: string;
}

export interface RequestPayoutRequest {
  amountMinor: number;
  bankAccountId?: string;
  bankName?: string;
  accountNumber?: string;
  accountName?: string;
}

export interface AddBankAccountRequest {
  bankName: string;
  accountNumber: string;
  accountName: string;
  isDefault?: boolean;
}

export interface PayoutDecisionRequest {
  note?: string;
  adjustmentMinor?: number;
}
