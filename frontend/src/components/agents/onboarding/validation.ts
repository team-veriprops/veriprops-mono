import { GovIdType, KycDetails, KycMethod } from "@/types/agent";
import { AgentWizardState, KycPhotos } from "./types";

/** What the KYC step needs beyond the saved state: the photos (never saved) and the ID types
 * the backend asks a document photo of (public config). */
export interface KycRules {
  photos: KycPhotos;
  /** Undefined until public config has loaded: the step cannot be judged complete before. */
  documentIdTypes?: GovIdType[];
}

/** Whether this ID is one a reviewer checks from a photo of the document. */
export function kycNeedsDocument(kyc: KycDetails, documentIdTypes: GovIdType[]): boolean {
  return kyc.method === KycMethod.GOV_ID && !!kyc.idType && documentIdTypes.includes(kyc.idType);
}

function kycComplete(kyc: KycDetails, { photos, documentIdTypes }: KycRules): boolean {
  if (!documentIdTypes) return false;
  const details = kyc.method === KycMethod.BVN
    ? !!kyc.bvn && kyc.bvn.length >= 10
    : !!kyc.idType && !!kyc.idNumber;
  const document = !kycNeedsDocument(kyc, documentIdTypes) || !!photos.idDocument;
  return details && !!photos.selfie && document;
}

/** Whether the wizard may advance from `step` (PRD §3.1 per-step gating). */
export function canAdvanceStep(step: number, state: AgentWizardState, kyc: KycRules): boolean {
  switch (step) {
    case 0: // Roles — at least one
      return state.roles.length > 0;
    case 1: // KYC — the method's details, a selfie, and a document photo where one is needed
      return kycComplete(state.kyc, kyc);
    case 2: // Credentials — every credential-requiring role has a licence number
      return state.credentials.every((c) => !!c.licenceNumber);
    default:
      return true;
  }
}

/** Whether the final submission is allowed: truthfulness + terms accepted, and the KYC step
 * complete — a resumed draft never kept the photos, so they may still be missing. */
export function canSubmit(state: AgentWizardState, termsAccepted: boolean, kyc: KycRules): boolean {
  return state.truthfulnessConfirmed && termsAccepted && state.roles.length > 0 && kycComplete(state.kyc, kyc);
}
