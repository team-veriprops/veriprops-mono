import { HttpClient } from "@lib/FetchHttpClient";
import { SuccessResponse } from "@/types/models";
import type {
  AgentApplication,
} from "@components/agents/libs/agent-service";

export type AdminSubRole = "SUPER" | "OPERATIONS" | "FINANCE";
export type AdminInvitationStatus = "PENDING" | "ACCEPTED" | "EXPIRED" | "REVOKED";
export type AcceptInviteBranch =
  | "SIGNUP_REQUIRED"
  | "LOGIN_REQUIRED"
  | "ALREADY_ADMIN"
  | "ACCEPTED";

export interface AdminInvitation {
  id: string;
  email: string;
  subRole: AdminSubRole;
  status: AdminInvitationStatus;
  inviterAdminId: string;
  expiresAt: string;
  acceptedAt: string | null;
  createdAt: string;
}

export interface InviteAdminResult {
  invitation: AdminInvitation;
  rawToken: string;
}

export interface AcceptInviteResult {
  branch: AcceptInviteBranch;
  email: string;
  subRole: AdminSubRole | null;
}

export interface PageResponse<T> {
  status: string;
  code: string;
  items: T[];
  meta: {
    page: number;
    pageSize: number;
    count: number;
    total: number;
  };
}

export interface AdminAgentApplication extends AgentApplication {
  idDocUrl: string | null;
  selfieUrl: string | null;
  surveyorLicenceUrl: string | null;
  nbaLicenceUrl: string | null;
  userFirstName: string | null;
  userLastName: string | null;
  userEmail: string | null;
}

// ── Verification admin types ──

export type VerificationStatus =
  | "DRAFT" | "PAID" | "IN_PROGRESS" | "UNDER_REVIEW" | "COMPLETED"
  | "CANCELLED" | "FAILED" | "PAUSED" | "FLAGGED";
export type VerificationTier = "BASIC" | "STANDARD" | "PREMIUM";

export interface VerificationNote {
  id: string;
  verificationId: string;
  adminId: string;
  content: string;
  tags: string[];
  pinned: boolean;
  createdAt: string;
  updatedAt: string | null;
}

export interface AdminVerificationListItem {
  id: string;
  vid: string;
  customerId: string;
  tier: VerificationTier;
  status: VerificationStatus;
  state: string | null;
  lga: string | null;
  addressLine: string | null;
  submittedAt: string | null;
  paidAt: string | null;
  createdAt: string;
  updatedAt: string | null;
}

export interface AdminVerificationDetail extends AdminVerificationListItem {
  property: Record<string, unknown> | null;
  pricing: Record<string, unknown> | null;
  notes: VerificationNote[];
  completedAt: string | null;
}

// ── Task types ──

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

export interface AvailableAgent {
  agentId: string;
  userId: string;
  firstName: string | null;
  lastName: string | null;
  types: string[];
  coverageStates: string[];
  activeTaskCount: number;
  rating: number | null;
  isTrusted: boolean;
}

// ── Admin config types ──

export interface AdminConfig {
  id: string;
  key: string;
  value: string;
  description: string | null;
  updatedBy: string | null;
  updatedAt: string | null;
}

export class AdminService {
  private readonly inviteBase = "/users/admin-invitations";
  private readonly agentBase = "/users/agents";
  private readonly verificationBase = "/admin/verifications";
  private readonly taskBase = "/admin";
  private readonly configBase = "/admin/config";

  constructor(private readonly http: HttpClient) {}

  // ── Admin invitations ──
  inviteAdmin(payload: {
    email: string;
    subRole: AdminSubRole;
  }): Promise<SuccessResponse<InviteAdminResult>> {
    return this.http.post(this.inviteBase, payload);
  }

  listInvitations(status?: AdminInvitationStatus): Promise<PageResponse<AdminInvitation>> {
    const qs = status ? `?status=${status}` : "";
    return this.http.get(`${this.inviteBase}${qs}`);
  }

  revokeInvitation(invitationId: string): Promise<SuccessResponse<boolean>> {
    return this.http.post(`${this.inviteBase}/${invitationId}/revoke`, {});
  }

  acceptInvitation(token: string): Promise<SuccessResponse<AcceptInviteResult>> {
    return this.http.post(`${this.inviteBase}/accept`, { token });
  }

  // ── Agent application queue ──
  listAgentApplications(opts?: {
    status?: "PENDING" | "APPROVED" | "REJECTED";
    page?: number;
    pageSize?: number;
  }): Promise<PageResponse<AdminAgentApplication>> {
    const params = new URLSearchParams();
    if (opts?.status) params.set("status", opts.status);
    if (opts?.page) params.set("page", String(opts.page));
    if (opts?.pageSize) params.set("page_size", String(opts.pageSize));
    const qs = params.toString();
    return this.http.get(`${this.agentBase}/admin/applications${qs ? `?${qs}` : ""}`);
  }

  approveApplication(applicationId: string): Promise<SuccessResponse<AdminAgentApplication>> {
    return this.http.post(`${this.agentBase}/admin/applications/${applicationId}/approve`, {});
  }

  rejectApplication(
    applicationId: string,
    reason: string,
  ): Promise<SuccessResponse<AdminAgentApplication>> {
    return this.http.post(`${this.agentBase}/admin/applications/${applicationId}/reject`, { reason });
  }

  // ── Admin verifications ──

  listVerifications(opts?: {
    status?: string;
    tier?: string;
    state?: string;
    lga?: string;
    vid?: string;
    page?: number;
    pageSize?: number;
  }): Promise<PageResponse<AdminVerificationListItem>> {
    const p = new URLSearchParams();
    if (opts?.status) p.set("status", opts.status);
    if (opts?.tier) p.set("tier", opts.tier);
    if (opts?.state) p.set("state", opts.state);
    if (opts?.lga) p.set("lga", opts.lga);
    if (opts?.vid) p.set("vid", opts.vid);
    if (opts?.page) p.set("page", String(opts.page));
    if (opts?.pageSize) p.set("page_size", String(opts.pageSize));
    const qs = p.toString();
    return this.http.get(`${this.verificationBase}${qs ? `?${qs}` : ""}`);
  }

  getVerification(vid: string): Promise<SuccessResponse<AdminVerificationDetail>> {
    return this.http.get(`${this.verificationBase}/${vid}`);
  }

  pauseVerification(vid: string): Promise<SuccessResponse<AdminVerificationDetail>> {
    return this.http.post(`${this.verificationBase}/${vid}/pause`, {});
  }

  resumeVerification(vid: string): Promise<SuccessResponse<AdminVerificationDetail>> {
    return this.http.post(`${this.verificationBase}/${vid}/resume`, {});
  }

  cancelVerification(vid: string): Promise<SuccessResponse<AdminVerificationDetail>> {
    return this.http.post(`${this.verificationBase}/${vid}/cancel`, {});
  }

  failVerification(vid: string, reason: string): Promise<SuccessResponse<AdminVerificationDetail>> {
    return this.http.post(`${this.verificationBase}/${vid}/fail`, { reason });
  }

  setDelay(vid: string, delayHours: number, reason: string): Promise<SuccessResponse<AdminVerificationDetail>> {
    return this.http.post(`${this.verificationBase}/${vid}/delay`, { delayHours, reason });
  }

  addNote(vid: string, payload: { content: string; tags: string[]; pinned: boolean }): Promise<SuccessResponse<VerificationNote>> {
    return this.http.post(`${this.verificationBase}/${vid}/notes`, payload);
  }

  updateNote(vid: string, noteId: string, payload: { pinned: boolean; tags: string[] }): Promise<SuccessResponse<VerificationNote>> {
    return this.http.put(`${this.verificationBase}/${vid}/notes/${noteId}`, payload);
  }

  releaseToPool(vid: string): Promise<SuccessResponse<AdminVerificationDetail>> {
    return this.http.post(`${this.verificationBase}/${vid}/release-to-pool`, {});
  }

  // ── Admin tasks ──

  listTasksForVerification(vid: string): Promise<SuccessResponse<Task[]>> {
    return this.http.get(`${this.taskBase}/verifications/${vid}/tasks`);
  }

  assignTask(vid: string, role: string, agentId: string): Promise<SuccessResponse<Task>> {
    return this.http.post(`${this.taskBase}/verifications/${vid}/tasks/${role}/assign`, { agentId });
  }

  reassignTask(taskId: string, agentId: string, note?: string): Promise<SuccessResponse<Task>> {
    return this.http.post(`${this.taskBase}/tasks/${taskId}/reassign`, { agentId, note });
  }

  listAvailableAgents(opts?: { role?: string; state?: string }): Promise<SuccessResponse<AvailableAgent[]>> {
    const p = new URLSearchParams();
    if (opts?.role) p.set("role", opts.role);
    if (opts?.state) p.set("state", opts.state);
    const qs = p.toString();
    return this.http.get(`${this.taskBase}/agents/available${qs ? `?${qs}` : ""}`);
  }

  // ── Admin config ──

  listConfig(): Promise<SuccessResponse<AdminConfig[]>> {
    return this.http.get(this.configBase);
  }

  setConfig(key: string, value: string): Promise<SuccessResponse<AdminConfig>> {
    return this.http.put(`${this.configBase}/${key}`, { value });
  }
}
