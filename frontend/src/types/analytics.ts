// Analytics types — mirror backend camelCase DTOs (PRD §18.1). Backend derives every figure.
import { VerificationTier } from "@/types/verification";

export interface Funnel {
  created: number;
  submitted: number;
  paid: number;
  completed: number;
  submitRate: number;
  paymentRate: number;
  completionRate: number;
}

export interface TierTime {
  tier: VerificationTier;
  avgDays: number;
  completedCount: number;
}

export interface TierRevenue {
  tier: VerificationTier;
  revenueMinor: number;
  count: number;
}

export interface LocationRevenue {
  state: string;
  revenueMinor: number;
  count: number;
}

export interface Revenue {
  totalMinor: number;
  byTier: TierRevenue[];
  byLocation: LocationRevenue[];
}

export interface RegionalRow {
  state: string;
  active: number;
  completed: number;
  avgTrustScore?: number;
  revenueMinor: number;
}

export interface AgentTrendPoint {
  month: string;
  completedTasks: number;
  avgQuality?: number;
}

export interface AgentTrends {
  points: AgentTrendPoint[];
}
