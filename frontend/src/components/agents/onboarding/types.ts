import {
  AgentCoverageInput,
  AgentCredentialInput,
  AgentRole,
  GovIdType,
  KycMethod,
} from "@/types/agent";

/** Accumulated agent-onboarding wizard state (persisted per step as a draft). */
export interface AgentWizardState {
  roles: AgentRole[];
  kyc: {
    method: KycMethod;
    bvn?: string;
    idType?: GovIdType;
    idNumber?: string;
    selfieReference?: string;
    documentRef?: string;
  };
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
