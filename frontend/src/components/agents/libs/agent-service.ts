import { HttpClient } from "@lib/FetchHttpClient";
import { SuccessResponse } from "@/types/models";

export type AgentType = "FIELD" | "SURVEYOR" | "REGISTRY" | "LAWYER";
export type AgentApplicationStatus = "DRAFT" | "PENDING" | "APPROVED" | "REJECTED";
export type KycMethod = "BVN" | "ID_DOC";
export type IdDocType = "NIN" | "PASSPORT" | "DRIVERS_LICENCE" | "VOTERS_CARD";

export interface AgentApplication {
  id: string;
  userId: string;
  status: AgentApplicationStatus;
  types: AgentType[];
  kycMethod: KycMethod | null;
  bvnLast4: string | null;
  bvnVerifiedAt: string | null;
  idDocType: IdDocType | null;
  idDocUploaded: boolean;
  selfieUploaded: boolean;
  selfieMatchScore: number | null;
  surveyorLicenceNo: string | null;
  nbaLicenceNo: string | null;
  yearsOfExperience: number | null;
  coverageStates: string[];
  coverageLgas: string[];
  bio: string | null;
  submittedAt: string | null;
  reviewedAt: string | null;
  rejectionReason: string | null;
  createdAt: string;
  updatedAt: string | null;
}

export interface BvnVerificationResult {
  verified: boolean;
  bvnLast4: string;
  verificationId: string | null;
  failureReason: string | null;
}

export interface TypesStepRequest {
  types: AgentType[];
}

export interface BvnVerifyRequest {
  bvn: string;
}

export interface KycDocumentsRequest {
  idDocType: IdDocType;
  idDocUrl: string;
  selfieUrl: string;
}

export interface CredentialsStepRequest {
  surveyorLicenceNo?: string;
  surveyorLicenceUrl?: string;
  nbaLicenceNo?: string;
  nbaLicenceUrl?: string;
  yearsOfExperience?: number;
  coverageStates: string[];
  coverageLgas: string[];
  bio?: string;
}

export interface SubmitApplicationRequest {
  truthfulnessAcknowledged: boolean;
  agentTermsConsentVersion: string;
}

export class AgentService {
  private readonly base = "/users/agents";

  constructor(private readonly http: HttpClient) {}

  getMyApplication(): Promise<SuccessResponse<AgentApplication>> {
    return this.http.get(`${this.base}/me/application`);
  }

  saveTypesStep(payload: TypesStepRequest): Promise<SuccessResponse<AgentApplication>> {
    return this.http.post(`${this.base}/me/application/types`, payload);
  }

  verifyBvn(payload: BvnVerifyRequest): Promise<SuccessResponse<BvnVerificationResult>> {
    return this.http.post(`${this.base}/me/application/kyc/bvn`, payload);
  }

  uploadKycDocs(payload: KycDocumentsRequest): Promise<SuccessResponse<AgentApplication>> {
    return this.http.post(`${this.base}/me/application/kyc/documents`, payload);
  }

  saveCredentialsStep(
    payload: CredentialsStepRequest,
  ): Promise<SuccessResponse<AgentApplication>> {
    return this.http.post(`${this.base}/me/application/credentials`, payload);
  }

  submitApplication(
    payload: SubmitApplicationRequest,
  ): Promise<SuccessResponse<AgentApplication>> {
    return this.http.post(`${this.base}/me/application/submit`, payload);
  }
}
