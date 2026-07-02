import { HttpClient } from "@lib/FetchHttpClient";
import { Page, SuccessResponse } from "@/types/models";
import {
  AgentApplicationDetail,
  AgentApplicationDraft,
  AgentApplicationStatusView,
  AgentApplicationSummary,
  AgentRole,
  SubmitAgentApplicationRequest,
} from "@/types/agent";

/**
 * Frontend-facing agent onboarding API. Mirrors the backend controller at
 * `backend/main/app/domain/user/agent/controller.py` (URL shape `/users/agents/...`).
 */
export class AgentService {
  private readonly base = "/users/agents";

  constructor(private readonly http: HttpClient) {}

  getDraft(): Promise<SuccessResponse<AgentApplicationDraft | null>> {
    return this.http.get(`${this.base}/application/draft`);
  }

  saveDraft(step: number, payload: Record<string, unknown>): Promise<SuccessResponse<AgentApplicationDraft>> {
    return this.http.put(`${this.base}/application/draft`, { step, payload });
  }

  submit(payload: SubmitAgentApplicationRequest): Promise<SuccessResponse<AgentApplicationStatusView>> {
    return this.http.post(`${this.base}/application`, payload);
  }

  getMyStatus(): Promise<SuccessResponse<AgentApplicationStatusView | null>> {
    return this.http.get(`${this.base}/application`);
  }

  // ── Admin (RBAC: APPROVE_AGENT) ─────────────────────────────────
  listApplications(
    status: string | undefined,
    page: number,
    pageSize: number,
  ): Promise<SuccessResponse<Page<AgentApplicationSummary>>> {
    const search = new URLSearchParams();
    if (status) search.set("status", status);
    search.set("page", String(page));
    search.set("page_size", String(pageSize));
    return this.http.get(`${this.base}/applications?${search.toString()}`);
  }

  getApplication(id: string): Promise<SuccessResponse<AgentApplicationDetail>> {
    return this.http.get(`${this.base}/applications/${id}`);
  }

  approve(id: string, approvedRoles?: AgentRole[]): Promise<SuccessResponse<AgentApplicationDetail>> {
    return this.http.post(`${this.base}/applications/${id}/approve`, { approvedRoles });
  }

  reject(id: string, reason: string): Promise<SuccessResponse<AgentApplicationDetail>> {
    return this.http.post(`${this.base}/applications/${id}/reject`, { reason });
  }
}
