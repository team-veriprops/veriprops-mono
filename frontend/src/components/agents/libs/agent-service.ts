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

// ── Task + Evidence + Escalation types ──

export type TaskRole = "FIELD" | "SURVEYOR" | "REGISTRY" | "LAWYER";
export type TaskStatus =
  | "PENDING" | "ASSIGNED" | "ACCEPTED" | "IN_PROGRESS"
  | "SUBMITTED" | "APPROVED" | "REJECTED";

export interface Task {
  id: string;
  verificationId: string;
  role: TaskRole;
  agentId: string | null;
  status: TaskStatus;
  poolReleasedAt: string | null;
  acceptedAt: string | null;
  submittedAt: string | null;
  trustScore: number | null;
  draftPayload: Record<string, unknown> | null;
  createdAt: string;
  updatedAt: string | null;
}

export interface EvidenceItem {
  id: string;
  taskId: string;
  uploaderId: string;
  type: "PHOTO" | "VIDEO" | "DOCUMENT";
  fileUrl: string;
  gpsLat: number | null;
  gpsLng: number | null;
  capturedAt: string | null;
  createdAt: string;
}

export interface Escalation {
  id: string;
  taskId: string;
  reporterId: string;
  category: "INACCESSIBLE" | "SUSPICIOUS" | "SAFETY" | "CONFLICTING" | "OTHER";
  description: string;
  createdAt: string;
}

export class AgentService {
  private readonly base = "/users/agents";
  private readonly taskBase = "/agents/tasks";

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

  // ── Tasks ──

  getAvailableTasks(role: TaskRole, state?: string): Promise<SuccessResponse<Task[]>> {
    const p = new URLSearchParams({ role });
    if (state) p.set("state", state);
    return this.http.get(`${this.taskBase}/available?${p.toString()}`);
  }

  getActiveTasks(): Promise<SuccessResponse<Task[]>> {
    return this.http.get(`${this.taskBase}/active`);
  }

  getCompletedTasks(): Promise<SuccessResponse<Task[]>> {
    return this.http.get(`${this.taskBase}/completed`);
  }

  getTask(taskId: string): Promise<SuccessResponse<Task>> {
    return this.http.get(`${this.taskBase}/${taskId}`);
  }

  acceptTask(taskId: string): Promise<SuccessResponse<Task>> {
    return this.http.post(`${this.taskBase}/${taskId}/accept`, {});
  }

  declineTask(taskId: string): Promise<SuccessResponse<Task>> {
    return this.http.post(`${this.taskBase}/${taskId}/decline`, {});
  }

  saveDraft(taskId: string, payload: Record<string, unknown>): Promise<SuccessResponse<Task>> {
    return this.http.put(`${this.taskBase}/${taskId}/draft`, payload);
  }

  submitTask(taskId: string, payload: Record<string, unknown>): Promise<SuccessResponse<Task>> {
    return this.http.post(`${this.taskBase}/${taskId}/submit`, payload);
  }

  // ── Evidence ──

  uploadEvidence(
    taskId: string,
    formData: FormData,
  ): Promise<SuccessResponse<EvidenceItem>> {
    return this.http.post(`${this.taskBase}/${taskId}/evidence`, formData);
  }

  // ── Escalation ──

  reportEscalation(
    taskId: string,
    payload: { category: Escalation["category"]; description: string },
  ): Promise<SuccessResponse<Escalation>> {
    return this.http.post(`${this.taskBase}/${taskId}/escalation`, payload);
  }
}
