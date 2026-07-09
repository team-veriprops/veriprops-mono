// Customer report experience types (PRD §10) — mirror backend camelCase DTOs at
// app/domain/verification/report. Backend owns the verdict, trust band and section
// content; the frontend renders them and never recomputes.
import { VerificationTier } from "@/types/verification";

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
}
