// Customer tracking & evidence types (PRD §9) — mirror backend camelCase DTOs at
// app/domain/verification/tracking. Backend is the source of truth for all labels,
// SLA state and interim reassurance; the frontend renders them verbatim.
import { AgentRole } from "@/types/agent";
import { EvidenceKind } from "@/types/agentTask";
import { SlaHealth } from "@/types/adminVerification";
import { VerificationStatus, VerificationTier } from "@/types/verification";

/** Assigned agent as the customer may see them — first name + role only (§4.9/§9.5). */
export interface AssignedAgent {
  role: AgentRole;
  firstName: string;
  avatarUrl?: string;
  verified: boolean;
}

export interface TrackingTask {
  role: AgentRole;
  stateLabel: string; // Pending / In Progress / Completed / "Awaiting other stages"
  completed: boolean;
  locked: boolean;
  submittedAt?: string;
  approvedAt?: string;
}

export interface InterimMilestone {
  role: AgentRole;
  message: string; // provisional positive copy (§9.3)
  note?: string; // optional one-line admin note
  at?: string;
}

export interface CustomerEvidence {
  id: string;
  role: AgentRole;
  kind: EvidenceKind;
  url?: string; // presigned, short-lived
  mimeType?: string;
  contentSha256: string;
  gpsLatitude?: number;
  gpsLongitude?: number;
  capturedAt?: string;
  uploadedAt: string;
}

export interface SlaTracker {
  expectedDate?: string;
  health: SlaHealth;
  label?: string; // On track / Running late / Delayed
  businessDaysRemaining?: number;
  elapsedBusinessDays?: number;
  totalBusinessDays?: number;
}

export interface VerificationTracking {
  id: string;
  vid: string;
  tier?: VerificationTier;
  status: VerificationStatus;
  statusLabel: string;
  address?: string;
  paused: boolean;
  paidAt?: string;
  sla: SlaTracker;
  progressPercent: number;
  requiredTaskCount: number;
  approvedTaskCount: number;
  tasks: TrackingTask[];
  agents: AssignedAgent[];
  interimMilestones: InterimMilestone[];
  evidencePreview: CustomerEvidence[];
}

export interface VerificationListItem {
  id: string;
  vid: string;
  tier?: VerificationTier;
  status: VerificationStatus;
  statusLabel: string;
  address?: string;
  slaDueDate?: string;
  dateCreated: string;
}

/** Portal home summary (§9) — every count is derived by the backend. */
export interface CustomerDashboard {
  total: number;
  draft: number;
  awaitingPayment: number;
  inProgress: number;
  completed: number;
  statusCounts: Partial<Record<VerificationStatus, number>>;
  recent: VerificationListItem[];
}

/** SSE event names emitted by the backend (§4.9) — must match useVerificationStream. */
export enum VerificationStreamEventName {
  STATUS_CHANGED = "status_changed",
  TASK_UPDATED = "task_updated",
  CONFLICT_DETECTED = "conflict_detected",
  REPORT_RELEASED = "report_released",
  HEARTBEAT = "heartbeat",
}
