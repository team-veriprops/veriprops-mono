import { HttpClient } from "@lib/FetchHttpClient";
import { Page, SuccessResponse } from "@/types/models";
import {
  AdminInvitationSummary,
  AdminSubRole,
  AdminTeamPage,
  InvitePreview,
} from "@/types/admin";

/**
 * Admin onboarding & team management API. Mirrors the backend controllers at
 * `app/domain/user/admin_invitation` and `app/domain/user/admin_team`
 * (URL shape `/users/admins/...`).
 */
export class AdminService {
  private readonly base = "/users/admins";

  constructor(private readonly http: HttpClient) {}

  inviteAdmin(
    email: string,
    subRole: AdminSubRole,
    firstName?: string,
    lastName?: string,
  ): Promise<SuccessResponse<{ inviteUrl: string }>> {
    return this.http.post(`${this.base}/invitations`, { email, subRole, firstName, lastName });
  }

  listInvitations(page: number, pageSize: number): Promise<SuccessResponse<Page<AdminInvitationSummary>>> {
    return this.http.get(`${this.base}/invitations?page=${page}&page_size=${pageSize}`);
  }

  revokeInvitation(id: string): Promise<SuccessResponse<boolean>> {
    return this.http.post(`${this.base}/invitations/${id}/revoke`, {});
  }

  previewInvitation(token: string): Promise<SuccessResponse<InvitePreview>> {
    return this.http.get(`${this.base}/invitations/preview/${token}`);
  }

  acceptInvitation(token: string): Promise<SuccessResponse<{ subRole: string }>> {
    return this.http.post(`${this.base}/invitations/accept`, { token });
  }

  listTeam(
    page: number,
    pageSize: number,
    query?: string,
    subRole?: string,
  ): Promise<SuccessResponse<AdminTeamPage>> {
    const params = new URLSearchParams();
    params.set("page", String(page));
    params.set("page_size", String(pageSize));
    if (query) params.set("query", query);
    if (subRole) params.set("sub_role", subRole);
    return this.http.get(`${this.base}/team?${params.toString()}`);
  }

  changeSubRole(userId: string, subRole: AdminSubRole): Promise<SuccessResponse<boolean>> {
    return this.http.post(`${this.base}/team/${userId}/sub-role`, { subRole });
  }

  deactivateMember(userId: string): Promise<SuccessResponse<boolean>> {
    return this.http.post(`${this.base}/team/${userId}/deactivate`, {});
  }
}
