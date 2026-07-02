import { KycMethod } from "@/types/agent";
import { AgentWizardState } from "./types";

/** Whether the wizard may advance from `step` (PRD §3.1 per-step gating). */
export function canAdvanceStep(step: number, state: AgentWizardState): boolean {
  switch (step) {
    case 0: // Roles — at least one
      return state.roles.length > 0;
    case 1: // KYC — method-specific required fields
      return state.kyc.method === KycMethod.BVN
        ? !!state.kyc.bvn && state.kyc.bvn.length >= 10
        : !!state.kyc.idType && !!state.kyc.idNumber;
    case 2: // Credentials — every credential-requiring role has a licence number
      return state.credentials.every((c) => !!c.licenceNumber);
    default:
      return true;
  }
}

/** Whether the final submission is allowed (truthfulness + terms accepted). */
export function canSubmit(state: AgentWizardState, termsAccepted: boolean): boolean {
  return state.truthfulnessConfirmed && termsAccepted && state.roles.length > 0;
}
