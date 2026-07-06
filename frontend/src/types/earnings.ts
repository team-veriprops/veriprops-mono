import { AgentRole } from "@/types/agent";
import { VerificationTier } from "@/types/verification";
import { TransactionCurrency } from "@/types/models";

/** Agent earnings dashboard figures (§15.1) — all in integer minor units (kobo). */
export interface EarningsSummary {
  availableMinor: number;
  clearingMinor: number;
  inReserveMinor: number;
  onHoldMinor: number;
  lifetimeEarnedMinor: number;
  totalPaidMinor: number;
  pendingPayoutMinor: number;
  currency: TransactionCurrency;
}

export type CommissionStatus = "CLEARING" | "AVAILABLE" | "FROZEN" | "REVERSED";

/** One commission line in the per-job earnings breakdown (§15.1). */
export interface EarningJob {
  id: string;
  verificationId: string;
  role: AgentRole;
  tier: VerificationTier;
  amountMinor: number;
  reserveAmountMinor: number;
  status: CommissionStatus;
  cleared: boolean;
  reserveReleased: boolean;
  clearingUntil?: string | null;
  reserveUntil?: string | null;
  dateCreated: string;
}
