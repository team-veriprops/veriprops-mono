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

// ─── WhatsApp channel (PRD §7.10, WA-43) ───────────────────────────

/** One bar in a §7.10 breakdown — a widget page code, or an escalation reason. */
export interface ChannelCount {
  label: string;
  count: number;
}

/**
 * Meta's verdict on our sending number (D81). `syncedAt` is rendered beside the rating
 * rather than hidden: a GREEN we have not refreshed for a week is a different fact from
 * a GREEN from this morning, and `syncError` is what says which one you are looking at.
 */
export interface WhatsAppNumberHealth {
  qualityRating: string;
  messagingLimitTier?: string;
  syncedAt?: string;
  syncError?: string;
}

/**
 * §7.10's seven channel metrics over one window.
 *
 * Rates arrive alongside the counts behind them, and both are rendered: "60%" over three
 * conversations is a very different thing from the same figure over three hundred, and an
 * admin who cannot see which is which will act on the wrong one.
 */
export interface WhatsAppChannelAnalytics {
  windowDays: number;

  intakeCompleted: number;
  paymentCompleted: number;
  seamConversionRate: number;

  enquiries: number;
  enquiriesByPageCode: ChannelCount[];

  intakeStarted: number;
  enquiryToIntakeRate: number;

  escalations: number;
  escalationRate: number;
  escalationsByReason: ChannelCount[];

  linkedNumbers: number;
  utilityOptIns: number;
  marketingOptIns: number;
  utilityOptInRate: number;
  marketingOptInRate: number;

  numberHealth?: WhatsAppNumberHealth;
  voiceNotes: number;
}
