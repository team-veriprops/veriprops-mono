import { HttpClient } from "@lib/FetchHttpClient";
import { Page, SuccessResponse } from "@/types/models";

export type PaymentMethod = "CARD" | "BANK_TRANSFER" | "WIRE";
export type PaymentStatus =
  | "INITIATED"
  | "PROCESSING"
  | "SUCCEEDED"
  | "FAILED"
  | "PENDING_TRANSFER"
  | "PENDING_WIRE";

export interface Payment {
  id: string;
  verificationId: string;
  provider: "FLUTTERWAVE" | "PAYSTACK";
  method: PaymentMethod;
  status: PaymentStatus;
  amountMinor: number;
  currency: string;
  providerRef: string | null;
  failureReason: string | null;
  wireProofUrl: string | null;
  dateCreated: string;
  dateUpdated: string | null;
}

export interface CustomerPayment extends Payment {
  vid: string;
}

export interface InitiatePaymentResult {
  payment: Payment;
  checkoutUrl: string | null;
  instructions: Record<string, unknown> | null;
}

export class PaymentService {
  private readonly base = "/payments";

  constructor(private readonly http: HttpClient) {}

  initiate(payload: {
    verificationId: string;
    method: PaymentMethod;
    redirectUrl?: string;
  }): Promise<SuccessResponse<InitiatePaymentResult>> {
    return this.http.post(`${this.base}/initiate`, payload);
  }

  get(id: string): Promise<SuccessResponse<Payment>> {
    return this.http.get(`${this.base}/${id}`);
  }

  uploadWireProof(
    id: string,
    payload: { proofUrl: string },
  ): Promise<SuccessResponse<Payment>> {
    return this.http.post(`${this.base}/${id}/wire-proof`, payload);
  }

  listForCustomer(page = 0, pageSize = 20): Promise<SuccessResponse<Page<CustomerPayment>>> {
    return this.http.get(`${this.base}/me?page=${page}&page_size=${pageSize}`);
  }
}
