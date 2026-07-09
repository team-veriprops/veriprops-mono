// Referral types — mirror backend camelCase DTOs (PRD §17.1). Backend owns all amounts
// (kobo) and eligibility; the frontend renders what it receives.

export enum ReferralCreditStatus {
  PENDING = "PENDING",
  CLEARED = "CLEARED",
  VOID = "VOID",
}

export interface ReferralCredit {
  id: string;
  inviteeUserId: string;
  verificationId: string;
  amountMinor: number;
  status: ReferralCreditStatus;
  clearingUntil?: string;
  clearedAt?: string;
  dateCreated: string;
}

export interface ReferralSummary {
  code: string;
  sharePath: string;
  referralCreditNgn: number;
  availableCreditMinor: number;
  pendingCreditMinor: number;
  lifetimeCreditMinor: number;
  credits: ReferralCredit[];
}
