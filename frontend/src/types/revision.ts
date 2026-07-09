// Revision / re-verification / dispute types (PRD §14) — mirror the backend camelCase DTOs
// at app/domain/verification/{recheck,upgrade,dispute}. Backend owns pricing, windows,
// state transitions, and version bumps; the frontend renders what it receives.
import { VerificationTier } from "@/types/verification";
import { AgentRole } from "@/types/agent";

// ── Re-check (§14.1) ──────────────────────────────────────────────
export enum RecheckStatus {
  PENDING = "PENDING",
  APPROVED = "APPROVED",
  REJECTED = "REJECTED",
  STARTED = "STARTED",
}

export interface Recheck {
  id: string;
  verificationId: string;
  reason: string;
  documents?: unknown[];
  scopeRoles?: string[];
  status: RecheckStatus;
  priceMinor: number;
  paymentId?: string;
  checkoutUrl?: string;
  decisionNote?: string;
  dateCreated: string;
}

export interface RequestRecheckRequest {
  reason: string;
  documents?: Record<string, unknown>[];
}

export interface DecideRecheckRequest {
  approve: boolean;
  scopeRoles?: AgentRole[];
  note?: string;
}

// ── Tier upgrade (§14.2) ──────────────────────────────────────────
export enum UpgradeStatus {
  PENDING = "PENDING",
  PAID = "PAID",
  CANCELLED = "CANCELLED",
}

export interface Upgrade {
  id: string;
  verificationId: string;
  fromTier: VerificationTier;
  toTier: VerificationTier;
  deltaMinor: number;
  status: UpgradeStatus;
  paymentId?: string;
  checkoutUrl?: string;
  dateCreated: string;
}

export interface RequestUpgradeRequest {
  toTier: VerificationTier;
}

// ── Dispute (§14.3) ───────────────────────────────────────────────
export enum DisputeStatus {
  OPEN = "OPEN",
  RESOLVED = "RESOLVED",
}

export enum DisputeOutcome {
  REJECTED = "REJECTED",
  FULL_REFUND = "FULL_REFUND",
  PARTIAL_RECHECK = "PARTIAL_RECHECK",
}

export enum DisputeType {
  INACCURATE_FINDING = "INACCURATE_FINDING",
  MISSING_CHECK = "MISSING_CHECK",
  AGENT_CONDUCT = "AGENT_CONDUCT",
  OTHER = "OTHER",
}

export interface Dispute {
  id: string;
  verificationId: string;
  disputeType: DisputeType;
  description: string;
  evidence?: unknown[];
  status: DisputeStatus;
  targetRole?: AgentRole;
  agentDefenceText?: string;
  agentDefenceAt?: string;
  resolutionOutcome?: DisputeOutcome;
  resolutionNote?: string;
  resolvedAt?: string;
  dateCreated: string;
}

export interface OpenDisputeRequest {
  disputeType: DisputeType;
  description: string;
  evidence?: Record<string, unknown>[];
  targetRole?: AgentRole;
}

export interface ResolveDisputeRequest {
  outcome: DisputeOutcome;
  note: string;
  scopeRoles?: AgentRole[];
}
