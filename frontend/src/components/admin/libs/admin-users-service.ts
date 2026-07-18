import { HttpClient } from "@lib/FetchHttpClient";
import { Page, SuccessResponse } from "@/types/models";
import { AdminUserDetail, AdminUserSummary } from "@/types/admin";
import { TrustStatus } from "@components/website/auth/models";

export interface AdminUsersListParams {
  page: number;
  pageSize: number;
  query?: string;
  persona?: string;
  userType?: string;
  trustStatus?: string;
  accountStatus?: string;
}

/**
 * Admin user-management API (PRD §4.2). Mirrors the backend controller at
 * `app/domain/user/admin_users` (URL shape `/users/admins/users/...`).
 */
export class AdminUsersService {
  private readonly base = "/users/admins/users";

  constructor(private readonly http: HttpClient) {}

  listUsers(params: AdminUsersListParams): Promise<SuccessResponse<Page<AdminUserSummary>>> {
    const search = new URLSearchParams();
    search.set("page", String(params.page));
    search.set("page_size", String(params.pageSize));
    if (params.query) search.set("query", params.query);
    if (params.persona) search.set("persona", params.persona);
    if (params.userType) search.set("user_type", params.userType);
    if (params.trustStatus) search.set("trust_status", params.trustStatus);
    if (params.accountStatus) search.set("account_status", params.accountStatus);
    return this.http.get(`${this.base}?${search.toString()}`);
  }

  getUserDetail(userId: string): Promise<SuccessResponse<AdminUserDetail>> {
    return this.http.get(`${this.base}/${userId}`);
  }

  suspendUser(userId: string, reason: string): Promise<SuccessResponse<boolean>> {
    return this.http.post(`${this.base}/${userId}/suspend`, { reason });
  }

  reactivateUser(userId: string): Promise<SuccessResponse<boolean>> {
    return this.http.post(`${this.base}/${userId}/reactivate`, {});
  }

  forcePasswordReset(userId: string): Promise<SuccessResponse<boolean>> {
    return this.http.post(`${this.base}/${userId}/password-reset`, {});
  }

  setTrustStatus(userId: string, trustStatus: TrustStatus): Promise<SuccessResponse<boolean>> {
    return this.http.post(`${this.base}/${userId}/trust-status`, { trustStatus });
  }
}
