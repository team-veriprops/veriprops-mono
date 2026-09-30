/**
 * Closing a paid case and Finance's refund approvals (backend `verification/closure/` and
 * `payment/refund_request/`, PRD §6.4, §8.5). The backend computes every amount; the UI shows
 * the quote and asks the admin to confirm it.
 */
import { AgentRole } from "@/types/agent";
import { RefundOutcome, TaskState } from "@/types/adminVerification";
import { TransactionCurrency } from "@/types/models";
import { VerificationStatus } from "@/types/verification";

/** Why a paid case is closing: the row of the PRD refund table it falls under. */
export enum CloseReason {
  CUSTOMER_WITHDREW = "CUSTOMER_WITHDREW",
  DUPLICATE = "DUPLICATE",
  CANNOT_DELIVER = "CANNOT_DELIVER",
  FRAUD = "FRAUD",
  PROPERTY_INACCESSIBLE = "PROPERTY_INACCESSIBLE",
}

export interface CloseCaseRequest {
  reason: CloseReason;
  note: string;
  /** PROPERTY_INACCESSIBLE only: the refund set on the evidence, and that evidence. */
  amountMinor?: number;
  evidenceRef?: string;
}

export interface ClosureAgentImpact {
  taskId: string;
  role: AgentRole;
  agentId?: string | null;
  state: TaskState;
  /** Submitted work is paid its role's fixed commission; anything else is cancelled unpaid. */
  paid: boolean;
}

export interface ClosureQuote {
  reason: CloseReason;
  /** The contractual currency every amount here is in (the case's own). */
  currency: TransactionCurrency;
  refundableMinor: number;
  refundMinor: number;
  resultingStatus: VerificationStatus;
  /** Money goes back: the case waits on hold for Finance's approval. */
  requiresApproval: boolean;
  agents: ClosureAgentImpact[];
}

export interface ClosureResult {
  status: VerificationStatus;
  onHold: boolean;
  refundMinor: number;
  currency: TransactionCurrency;
  refundRequestId?: string | null;
}

export enum RefundSource {
  CASE_CLOSURE = "CASE_CLOSURE",
  DISPUTE_UPHELD = "DISPUTE_UPHELD",
  LATE_CHARGE = "LATE_CHARGE",
}

export enum RefundRequestStatus {
  PENDING = "PENDING",
  APPROVED = "APPROVED",
  REJECTED = "REJECTED",
}

export interface RefundRequest {
  id: string;
  verificationId: string;
  vid: string;
  customerId: string;
  source: RefundSource;
  status: RefundRequestStatus;
  amountMinor: number;
  currency: TransactionCurrency;
  reason?: string | null;
  note?: string | null;
  evidenceRef?: string | null;
  requestedBy?: string | null;
  decidedBy?: string | null;
  decidedAt?: string | null;
  decisionNote?: string | null;
  dateCreated: string;
}

export interface RefundDecision {
  request: RefundRequest;
  /** Approval only: what the gateways did. A refused charge waits in the refunds-to-retry list. */
  outcome?: RefundOutcome | null;
}
