// Agent onboarding & KYC types — mirror backend camelCase DTOs (PRD §3.1–3.2, §3.3a).
// Backend is the source of truth; keep these enums in sync with
// backend/main/app/domain/user/agent/models.py and appodus_utils/integrations/kyc/models.py.

export enum AgentRole {
  REGISTRY = "REGISTRY",
  FIELD = "FIELD",
  SURVEYOR = "SURVEYOR",
  LAWYER = "LAWYER",
}

export enum AgentApplicationStatus {
  PENDING = "PENDING",
  APPROVED = "APPROVED",
  REJECTED = "REJECTED",
}

export enum CredentialType {
  SURVEYOR_LICENCE = "SURVEYOR_LICENCE",
  NBA_LICENCE = "NBA_LICENCE",
}

export enum CredentialStatus {
  PENDING = "PENDING",
  VERIFIED = "VERIFIED",
  EXPIRED = "EXPIRED",
  SUSPENDED = "SUSPENDED",
}

export enum KycMethod {
  BVN = "BVN",
  GOV_ID = "GOV_ID",
}

export enum GovIdType {
  NIN = "NIN",
  PASSPORT = "PASSPORT",
  DRIVERS_LICENCE = "DRIVERS_LICENCE",
  VOTERS_CARD = "VOTERS_CARD",
}

export enum KycProvider {
  STUB = "STUB",
  DOJAH = "DOJAH",
}

export enum KycResultStatus {
  VERIFIED = "VERIFIED",
  FAILED = "FAILED",
  NEEDS_REVIEW = "NEEDS_REVIEW",
  PENDING = "PENDING",
}

// Roles that require a professional licence before approval (PRD §3.1 step 3).
export const ROLE_REQUIRED_CREDENTIAL: Partial<Record<AgentRole, CredentialType>> = {
  [AgentRole.SURVEYOR]: CredentialType.SURVEYOR_LICENCE,
  [AgentRole.LAWYER]: CredentialType.NBA_LICENCE,
};

export interface AgentCoverageInput {
  state: string;
  lga?: string;
  place?: string;
  travelRadiusKm?: number;
}

export interface AgentCredentialInput {
  role: AgentRole;
  credentialType: CredentialType;
  licenceNumber?: string;
  documentRef?: string;
  expiryDate?: string;
}

export interface KycSubmission {
  method: KycMethod;
  bvn?: string;
  idType?: GovIdType;
  idNumber?: string;
  selfieReference?: string;
  documentRef?: string;
}

export interface SubmitAgentApplicationRequest {
  roles: AgentRole[];
  kyc: KycSubmission;
  credentials: AgentCredentialInput[];
  coverage: AgentCoverageInput[];
  bio?: string;
  yearsExperience?: number;
  truthfulnessConfirmed: boolean;
  agentTermsVersion: string;
}

export interface AgentApplicationStatusView {
  status: AgentApplicationStatus;
  roles: AgentRole[];
  approvedRoles: AgentRole[];
  activeRoles: AgentRole[];
  rejectionReason?: string;
  submittedAt?: string;
}

// Draft persisted per-step so the wizard resumes after a refresh/relogin.
export interface AgentApplicationDraft {
  step: number;
  payload: Record<string, unknown>;
  dateUpdated?: string;
}

export interface AgentCredentialView {
  role: AgentRole;
  credentialType: CredentialType;
  licenceNumber?: string;
  expiryDate?: string;
  status: CredentialStatus;
}

export interface KycRecordView {
  provider: KycProvider;
  method: KycMethod;
  status: KycResultStatus;
  score?: number;
  summary?: string;
  verifiedAt?: string;
}

// Row in the admin applications DataTable.
export interface AgentApplicationSummary {
  id: string;
  userId: string;
  applicantName: string;
  roles: AgentRole[];
  status: AgentApplicationStatus;
  submittedAt?: string;
}

// Admin DetailDrawer view.
export interface AgentApplicationDetail {
  id: string;
  userId: string;
  applicantName: string;
  applicantEmail: string;
  roles: AgentRole[];
  approvedRoles: AgentRole[];
  status: AgentApplicationStatus;
  rejectionReason?: string;
  bio?: string;
  yearsExperience?: number;
  submittedAt?: string;
  credentials: AgentCredentialView[];
  coverage: AgentCoverageInput[];
  kyc?: KycRecordView;
}
