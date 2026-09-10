// Agent task-execution types (PRD §12.1, §12.2) — mirror backend camelCase DTOs at
// app/domain/verification/task. Backend owns task state + derivation.
import { AgentRole } from "@/types/agent";
import { TaskState, TaskAssignmentMode } from "@/types/adminVerification";
import { VerificationTier } from "@/types/verification";

export { TaskState } from "@/types/adminVerification";

export enum EvidenceKind {
  PHOTO = "PHOTO",
  VIDEO = "VIDEO",
  DOCUMENT = "DOCUMENT",
  SIGNATURE = "SIGNATURE",
  CERTIFICATE = "CERTIFICATE",
}

export interface AgentTask {
  id: string;
  verificationId: string;
  role: AgentRole;
  tier: VerificationTier;
  state: TaskState;
  inPool: boolean;
  assignmentMode?: TaskAssignmentMode;
  acceptDeadlineAt?: string;
  remoteBonusMinor?: number;
  submissionPayload?: Record<string, unknown>;
  rejectionReason?: string;
  evidenceCount: number;
  assignedAt?: string;
  acceptedAt?: string;
  submittedAt?: string;
}

/** Agent home summary (§12) — backend-derived counts over the agent's own tasks. */
export interface AgentDashboard {
  assigned: number;
  active: number;
  submitted: number;
  approved: number;
  total: number;
  stateCounts: Partial<Record<TaskState, number>>;
}

export interface EvidenceItem {
  id: string;
  taskId: string;
  verificationId: string;
  kind: EvidenceKind;
  storageUrl?: string;
  mimeType?: string;
  sizeBytes?: number;
  contentSha256: string;
  gpsLatitude?: number;
  gpsLongitude?: number;
  capturedAt?: string;
  uploadedAt: string;
}

// The per-role submission form fields (mirrors the backend validator's required set, §12.2).
export const ROLE_FORM_FIELDS: Record<AgentRole, { key: string; label: string; required: boolean }[]> = {
  [AgentRole.REGISTRY]: [
    { key: "registered_owner", label: "Registered owner", required: true },
    { key: "title_search_result", label: "Title search result", required: true },
    { key: "search_reference", label: "Search reference", required: true },
    { key: "encumbrances", label: "Encumbrances (notes)", required: false },
  ],
  [AgentRole.FIELD]: [
    { key: "occupancy_status", label: "Occupancy status", required: true },
    { key: "physical_condition", label: "Physical condition", required: true },
    { key: "notes", label: "Notes", required: false },
  ],
  [AgentRole.SURVEYOR]: [
    { key: "area_sqm", label: "Area (sqm)", required: true },
    { key: "beacon_status", label: "Beacon status", required: true },
    { key: "notes", label: "Notes", required: false },
  ],
  [AgentRole.LAWYER]: [
    { key: "legal_opinion", label: "Legal opinion", required: true },
    { key: "risk_level", label: "Risk level", required: true },
    { key: "recommendation", label: "Recommendation", required: true },
  ],
};
