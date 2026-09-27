import { HttpClient } from "@lib/FetchHttpClient";
import { DEFAULT_PAGE_SIZE } from "@lib/config/app";
import { Page, SuccessResponse } from "@/types/models";
import { Payment } from "@/types/verification";

/**
 * Finance's refund recovery (PRD §8.5, §18.1). Mirrors `admin_payment_router` in
 * app/domain/payment/controller.py — RBAC REFUND_PAYMENT.
 */
export class AdminPaymentService {
  constructor(private readonly http: HttpClient) {}

  /** Settled payments on failed or refunded verifications: refunds a gateway refused. */
  listRefundRetries(page = 0, pageSize = DEFAULT_PAGE_SIZE): Promise<SuccessResponse<Page<Payment>>> {
    return this.http.get(`/admin/payments/refund-retries?page=${page}&page_size=${pageSize}`);
  }

  retryRefund(paymentId: string): Promise<SuccessResponse<Payment>> {
    return this.http.post(`/admin/payments/${paymentId}/refund`);
  }
}
