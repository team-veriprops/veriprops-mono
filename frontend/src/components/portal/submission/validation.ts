import { PropertyKind } from "@/types/verification";
import { SubmissionState } from "./types";

/** Per-step gating for the submission wizard (PRD §5.1). The landmark free-text
 *  is a mandatory escape valve, so a resolved address OR a landmark satisfies 1C. */
export function canAdvanceSubmissionStep(step: number, state: SubmissionState): boolean {
  switch (step) {
    case 0: // Property — a type and either an address or a landmark
      return (
        !!state.property.propertyType &&
        (state.property.address.trim().length > 0 || state.property.landmark.trim().length > 0)
      );
    case 1: // Tier & pricing — a tier chosen
      return !!state.tier;
    case 2: // Consent — VERIFICATION_TERMS accepted
      return state.consentAccepted;
    default:
      return true;
  }
}

export function isBuilding(kind: PropertyKind): boolean {
  return kind === PropertyKind.BUILDING;
}
