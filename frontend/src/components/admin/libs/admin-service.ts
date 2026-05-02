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

export class AdminService {
  private readonly inviteBase = "/users/admin-invitations";
  private readonly agentBase = "/users/agents";

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
}
