import { HttpClient } from "@lib/FetchHttpClient";
import { Page, SuccessResponse } from "@/types/models";
import { AgentRole } from "@/types/agent";
import {
  AdminDashboard,
  AdminNoteCategory,
  ChargebackDto,
  VerificationDetail,
  VerificationListFilters,
  VerificationSummary,
} from "@/types/adminVerification";

/**
 * Admin verification control-panel API. Mirrors the backend controller at
 * `app/domain/verification/admin` (URL shape `/admin/verifications/...`) and the
 * chargeback sub-process endpoints (§6a). Backend owns status/SLA/task derivation.
 */
export class AdminVerificationService {
  private readonly base = "/admin/verifications";

  constructor(private readonly http: HttpClient) {}

  list(
    filters: VerificationListFilters,
    page: number,
    pageSize: number,
  ): Promise<SuccessResponse<Page<VerificationSummary>>> {
    const params = new URLSearchParams();
    if (filters.status) params.set("status", filters.status);
    if (filters.tier) params.set("tier", filters.tier);
    if (filters.stateRegion) params.set("state_region", filters.stateRegion);
    if (filters.overdueOnly) params.set("overdue_only", "true");
    if (filters.query) params.set("query", filters.query);
    params.set("page", String(page));
    params.set("page_size", String(pageSize));
    return this.http.get(`${this.base}?${params.toString()}`);
  }

  /** Admin operations home summary (§6) — backend-owned queue health rollups. */
  getSummary(): Promise<SuccessResponse<AdminDashboard>> {
    return this.http.get(`${this.base}/summary`);
  }

  getDetail(verificationId: string): Promise<SuccessResponse<VerificationDetail>> {
    return this.http.get(`${this.base}/${verificationId}`);
  }

  assign(
    verificationId: string,
    role: AgentRole,
    agentId: string,
  ): Promise<SuccessResponse<VerificationDetail>> {
    return this.http.post(`${this.base}/${verificationId}/tasks/${role}/assign`, { agentId });
  }

  pause(verificationId: string): Promise<SuccessResponse<VerificationDetail>> {
    return this.http.post(`${this.base}/${verificationId}/pause`, {});
  }

  resume(verificationId: string): Promise<SuccessResponse<VerificationDetail>> {
    return this.http.post(`${this.base}/${verificationId}/resume`, {});
  }

  cancel(verificationId: string, reason: string): Promise<SuccessResponse<VerificationDetail>> {
    return this.http.post(`${this.base}/${verificationId}/cancel`, { reason });
  }

  setDelay(
    verificationId: string,
    extraBusinessDays: number,
    reason?: string,
  ): Promise<SuccessResponse<VerificationDetail>> {
    return this.http.post(`${this.base}/${verificationId}/delay`, { extraBusinessDays, reason });
  }

  addNote(
    verificationId: string,
    category: AdminNoteCategory,
    body: string,
    pinned = false,
  ): Promise<SuccessResponse<VerificationDetail>> {
    return this.http.post(`${this.base}/${verificationId}/notes`, { category, body, pinned });
  }

  submitRebuttal(chargebackId: string): Promise<SuccessResponse<ChargebackDto>> {
    return this.http.post(`${this.base}/chargebacks/${chargebackId}/rebuttal`, {});
  }

  resolveChargeback(chargebackId: string, won: boolean): Promise<SuccessResponse<ChargebackDto>> {
    return this.http.post(`${this.base}/chargebacks/${chargebackId}/resolve`, { won });
  }
}
