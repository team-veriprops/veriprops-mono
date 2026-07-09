// Report sharing types (PRD §13) — mirror the backend camelCase DTOs at
// app/domain/verification/share. Backend is the source of truth for what a public
// summary may contain (never the numeric score, full address, or agent/owner names).
import { VerificationTier, PropertyKind } from "@/types/verification";
import { CustomerReport } from "@/types/report";

export enum ShareType {
  LINK_SUMMARY = "LINK_SUMMARY",
  NAMED_FULL = "NAMED_FULL",
}

export enum PublicLookupState {
  SHARED = "SHARED",
  PRIVATE = "PRIVATE",
  IN_PROGRESS = "IN_PROGRESS",
  DISPUTED = "DISPUTED",
  NOT_FOUND = "NOT_FOUND",
}

export interface PublicSummary {
  state: PublicLookupState;
  message?: string;
  vid?: string;
  verified: boolean;
  trustBand?: string; // band only, never the number
  tier?: VerificationTier;
  propertyType?: PropertyKind;
  stateRegion?: string;
  lga?: string;
  reportVersion?: number;
  reportDate?: string;
}

export interface SharedReport {
  state: PublicLookupState;
  shareType?: ShareType;
  requiresAcknowledgement: boolean;
  summary?: PublicSummary;
  report?: CustomerReport;
}

export interface Share {
  id: string;
  verificationId: string;
  shareType: ShareType;
  recipientEmail?: string;
  token: string;
  shareUrl: string;
  expiresAt?: string;
  revokedAt?: string;
  firstViewedAt?: string;
  disclaimerAckedAt?: string;
  active: boolean;
  dateCreated: string;
}

export interface CreateShareRequest {
  shareType: ShareType;
  recipientEmail?: string;
  expiresInDays?: number;
}
