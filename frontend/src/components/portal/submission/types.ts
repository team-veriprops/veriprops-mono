import { TransactionCurrency } from "@/types/models";
import { PropertyKind, VerificationTier } from "@/types/verification";

/** Accumulated submission-wizard state (autosaved per step; VID/DRAFT on step-1 load). */
export interface SubmissionState {
  property: {
    propertyType: PropertyKind;
    address: string;
    landmark: string;
    state: string;
    latitude?: number;
    longitude?: number;
    placeId?: string;
    // Conditional facts (PRD §5.1) — Land vs Building specifics the agent verifies on the ground.
    details: Record<string, string>;
  };
  tier: VerificationTier;
  currency: TransactionCurrency;
  consentAccepted: boolean;
}

export const EMPTY_SUBMISSION: SubmissionState = {
  property: { propertyType: PropertyKind.LAND, address: "", landmark: "", state: "", details: {} },
  tier: VerificationTier.STANDARD,
  currency: TransactionCurrency.NGN,
  consentAccepted: false,
};

export const SUBMISSION_STEPS = ["Property", "Tier & Pricing", "Consent", "Payment"];
