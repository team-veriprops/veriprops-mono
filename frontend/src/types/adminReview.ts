// Admin review & report-release types (PRD §8) — mirror backend camelCase DTOs at
// app/domain/verification/review, report, scoring.
import { AgentRole } from "@/types/agent";
import { VerificationStatus, VerificationTier } from "@/types/verification";
import { TaskDto } from "@/types/adminVerification";

export enum ReportState {
  DRAFT = "DRAFT",
  RELEASED = "RELEASED",
  SUPERSEDED = "SUPERSEDED",
}

export interface ReportDto {
  id: string;
  verificationId: string;
  reportVersion: number;
  state: ReportState;
  compositeTrustScore?: number;
  findings?: Record<string, unknown>;
  releaseReason?: string;
  releasedAt?: string;
  supersededAt?: string;
  dateCreated: string;
}

/** How much a review conflict matters (backend `ConflictSeverity`): HIGH blocks release. */
export enum ConflictSeverity {
  HIGH = "HIGH",
  MEDIUM = "MEDIUM",
  LOW = "LOW",
}

export interface ReviewConflict {
  severity: ConflictSeverity;
  roles: AgentRole[];
  message: string;
}

export interface ReviewState {
  verificationId: string;
  vid: string;
  status: VerificationStatus;
  /** Whether the case can be closed from here (paid, unfinished, not already closing). */
  canClose: boolean;
  tier?: VerificationTier;
  tasks: TaskDto[];
  conflicts: ReviewConflict[];
  projectedTrustScore?: number;
  allApproved: boolean;
  releasable: boolean;
  report?: ReportDto;
  findings: Record<string, Record<string, unknown> | null>;
}

// ── Trust Score Weights (§8.3) ──
export interface TrustWeight {
  id: string;
  tier: VerificationTier;
  role: AgentRole;
  weightPercent: number;
  dateCreated: string;
}

export interface TierWeights {
  tier: VerificationTier;
  weights: TrustWeight[];
  totalPercent: number;
  valid: boolean;
}
