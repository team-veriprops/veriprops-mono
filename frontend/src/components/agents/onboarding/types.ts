import {
  AgentCoverageInput,
  AgentCredentialInput,
  AgentRole,
  KycDetails,
  KycMethod,
} from "@/types/agent";

/** The KYC photos, as base64 JPEG. Held apart from the wizard state so they are never saved
 * in the draft; after a resumed draft the applicant takes them again. */
export interface KycPhotos {
  selfie?: string;
  idDocument?: string;
}

/** Accumulated agent-onboarding wizard state (persisted per step as a draft). */
export interface AgentWizardState {
  roles: AgentRole[];
  // Saved in the draft, so it never holds a photo (see `KycPhotos`).
  kyc: KycDetails;
  credentials: AgentCredentialInput[];
  coverage: AgentCoverageInput[];
  bio?: string;
  yearsExperience?: number;
  truthfulnessConfirmed: boolean;
}

export const EMPTY_WIZARD_STATE: AgentWizardState = {
  roles: [],
  kyc: { method: KycMethod.BVN },
  credentials: [],
  coverage: [],
  bio: "",
  truthfulnessConfirmed: false,
};

export const AGENT_WIZARD_STEPS = ["Roles", "Identity (KYC)", "Credentials", "Review & submit"];
/** The identity step's index: where a resumed draft returns to retake the photos. */
export const KYC_STEP = 1;
