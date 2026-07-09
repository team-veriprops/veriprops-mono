import { AgentRole } from "@/types/agent";

export enum AvailabilityStatus {
  GREEN = "GREEN",
  AMBER = "AMBER",
  RED = "RED",
}

/** Aggregated reputation metrics (§16.1), all backend-derived. */
export interface AgentMetrics {
  totalJobs: number;
  completedJobs: number;
  completionRate: number; // 0–100
  accuracyScore: number; // 0–5
  avgQuality: number; // 0–100
  timelinessRate: number; // 0–100
  declineCount: number;
  compositeScore: number; // 0–100
  activeSince?: string | null;
}

export interface CoverageArea {
  state: string;
  lga?: string | null;
  place?: string | null;
  travelRadiusKm?: number | null;
}

export interface AgentProfileSummary {
  metrics: AgentMetrics;
  availability: AvailabilityStatus;
  effectiveAvailability: AvailabilityStatus;
  activeTaskCount: number;
  maxActiveTasks: number;
  approvedRoles: AgentRole[];
  activeRoles: AgentRole[];
  coverage: CoverageArea[];
  coverageFlaggedForReview: boolean;
}

/** One ranked assignment candidate (§16.1, admin-only). */
export interface SuggestedAgent {
  userId: string;
  name: string;
  compositeScore: number;
  accuracyScore: number;
  completionRate: number;
  timelinessRate: number;
  availability: AvailabilityStatus;
  activeTaskCount: number;
  coversArea: boolean;
  topAgent: boolean;
  lowPerformance: boolean;
}

export interface NigerianState {
  code: string;
  label: string;
}

export interface NigeriaLocations {
  states: NigerianState[];
}
