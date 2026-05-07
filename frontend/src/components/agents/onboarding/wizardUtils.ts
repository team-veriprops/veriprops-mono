import type { AgentApplication, AgentType } from "../libs/agent-service";

export function deriveResumeStep(application: AgentApplication): number {
  if (application.status !== "DRAFT") return 0;
  let step = 0;
  if (application.types.length > 0) step = 1;
  if (
    (application.kycMethod === "BVN" && !!application.bvnVerifiedAt) ||
    (application.kycMethod === "ID_DOC" &&
      application.idDocUploaded &&
      application.selfieUploaded)
  ) {
    step = 2;
  }
  if (application.coverageStates.length > 0) step = 3;
  return step;
}

export interface CredentialsValidationResult {
  valid: boolean;
  error: string | null;
}

export function validateCredentialsStep(
  types: AgentType[],
  fields: {
    surveyorLicenceNo: string;
    surveyorLicenceUrl: string;
    nbaLicenceNo: string;
    nbaLicenceUrl: string;
    coverageStates: string[];
    bio: string;
  },
): CredentialsValidationResult {
  if (types.includes("SURVEYOR") && (!fields.surveyorLicenceNo || !fields.surveyorLicenceUrl)) {
    return { valid: false, error: "Surveyor licence number and document are required." };
  }
  if (types.includes("LAWYER") && (!fields.nbaLicenceNo || !fields.nbaLicenceUrl)) {
    return { valid: false, error: "NBA licence number and document are required." };
  }
  if (fields.coverageStates.length === 0) {
    return { valid: false, error: "Select at least one coverage state." };
  }
  if (fields.bio.length > 300) {
    return { valid: false, error: "Bio must not exceed 300 characters." };
  }
  return { valid: true, error: null };
}
