import { HttpClient } from "@lib/FetchHttpClient";
import { DEFAULT_PAGE_SIZE } from "@lib/config/app";
import { Page, SuccessResponse } from "@/types/models";
import { AdminPayment, Payment, PaymentStatus } from "@/types/verification";

/** The server-side search and filter of finance's payments list. */
export interface PaymentListFilters {
  query?: string;
  status?: PaymentStatus;
}

/**
 * Finance's payments list and refund recovery (PRD §8.5, §18.1). Mirrors `admin_payment_router` in
 * app/domain/payment/controller.py — RBAC REFUND_PAYMENT.
 */
export class AdminPaymentService {
  constructor(private readonly http: HttpClient) {}

  /** Every charge, newest first; search (reference or VID) and filter run on the server. */
  list(page = 0, pageSize = DEFAULT_PAGE_SIZE, filters: PaymentListFilters = {}): Promise<SuccessResponse<Page<AdminPayment>>> {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (filters.query) params.set("query", filters.query);
    if (filters.status) params.set("status", filters.status);
    return this.http.get(`/admin/payments?${params.toString()}`);
  }

  /** Settled payments on failed, cancelled or refunded verifications: refunds a gateway refused. */
  listRefundRetries(page = 0, pageSize = DEFAULT_PAGE_SIZE): Promise<SuccessResponse<Page<Payment>>> {
    return this.http.get(`/admin/payments/refund-retries?page=${page}&page_size=${pageSize}`);
  }

  retryRefund(paymentId: string): Promise<SuccessResponse<Payment>> {
    return this.http.post(`/admin/payments/${paymentId}/refund`);
  }
}
