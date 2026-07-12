import { HttpClient } from "@lib/FetchHttpClient";
import { DEFAULT_PAGE_SIZE } from "@lib/config/app";
import { Page, SuccessResponse } from "@/types/models";
import { Payout, PayoutDecisionRequest } from "@/types/payout";

/**
 * Finance payout panel API (PRD §15.1). Mirrors the admin routes in
 * app/domain/payout/controller.py — RBAC APPROVE_PAYOUT.
 */
export class AdminPayoutService {
  constructor(private readonly http: HttpClient) {}

  listPayouts(page = 0, pageSize = DEFAULT_PAGE_SIZE, status?: string): Promise<SuccessResponse<Page<Payout>>> {
    const statusParam = status ? `&status=${status}` : "";
    return this.http.get(`/admin/payouts?page=${page}&page_size=${pageSize}${statusParam}`);
  }

  approve(payoutId: string, req: PayoutDecisionRequest = {}): Promise<SuccessResponse<Payout>> {
    return this.http.post(`/admin/payouts/${payoutId}/approve`, req);
  }

  hold(payoutId: string, req: PayoutDecisionRequest): Promise<SuccessResponse<Payout>> {
    return this.http.post(`/admin/payouts/${payoutId}/hold`, req);
  }

  adjust(payoutId: string, req: PayoutDecisionRequest): Promise<SuccessResponse<Payout>> {
    return this.http.post(`/admin/payouts/${payoutId}/adjust`, req);
  }

  reject(payoutId: string, req: PayoutDecisionRequest): Promise<SuccessResponse<Payout>> {
    return this.http.post(`/admin/payouts/${payoutId}/reject`, req);
  }
}
