import { HttpClient } from "@lib/FetchHttpClient";
import { DEFAULT_PAGE_SIZE } from "@lib/config/app";
import { Page, SuccessResponse } from "@/types/models";
import { RefundDecision, RefundRequest, RefundRequestStatus } from "@/types/closure";

/**
 * Finance's refund-approval queue (PRD §8.5, §18.1): every return of a customer's money waits
 * here. Mirrors `refund_request_router` in app/domain/payment/refund_request/controller.py —
 * RBAC REFUND_PAYMENT.
 */
export class RefundRequestService {
  constructor(private readonly http: HttpClient) {}

  /** Pending requests oldest first (the queue); any other view newest first (the record), unless sorted. */
  list(
    page = 0, pageSize = DEFAULT_PAGE_SIZE, status?: RefundRequestStatus, orderBy?: string,
  ): Promise<SuccessResponse<Page<RefundRequest>>> {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (status) params.set("status", status);
    if (orderBy) params.set("order_by", orderBy);
    return this.http.get(`/admin/refund-requests?${params.toString()}`);
  }

  /** Send the refund. A closing case is finished first; the outcome says what the gateways did. */
  approve(requestId: string, note?: string): Promise<SuccessResponse<RefundDecision>> {
    return this.http.post(`/admin/refund-requests/${requestId}/approve`, { note });
  }

  /** Send nothing; a closing case goes back to work. The note is required: the requester is told. */
  reject(requestId: string, note: string): Promise<SuccessResponse<RefundDecision>> {
    return this.http.post(`/admin/refund-requests/${requestId}/reject`, { note });
  }
}
