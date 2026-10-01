// Customer report experience types (PRD §10) — mirror backend camelCase DTOs at
// app/domain/verification/report. Backend owns the verdict, trust band and section
// content; the frontend renders them and never recomputes.
import { AgentRole } from "@/types/agent";
import { VerificationTier } from "@/types/verification";

/** What the report's owner may do next (§19.2, §19.3). The backend decides; the page renders. */
export interface CustomerReportActions {
  upgradeTiers: VerificationTier[];
  /** Parts of the work a dispute can name — naming one asks that task's agent for a defence. */
  disputeRoles: AgentRole[];
  disputeMinDescriptionChars: number;
}

export interface ReportSection {
  key: string;
  title: string;
  body: string;
  isLegalOpinion: boolean;
}

export interface CustomerReport {
  id: string;
  verificationId: string;
  vid: string;
  tier?: VerificationTier;
  address?: string;
  reportVersion: number;
  releasedAt?: string;
  superseded: boolean;
  trustScore?: number;
  trustBand?: string; // Safe / Caution / High Risk
  trustMeaning?: string;
  verdict: string;
  sections: ReportSection[];
  legalOpinionIncluded: boolean;
  acknowledged: boolean;
  /** The owner's next steps; absent on a shared copy. */
  actions?: CustomerReportActions | null;
}
