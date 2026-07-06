import { HttpClient } from "@lib/FetchHttpClient";
import { Page, SuccessResponse, TransactionCurrency } from "@/types/models";
import {
  GeoLocation,
  GeoSuggestion,
  Payment,
  PaymentMethodKind,
  PriceQuote,
  PriceRefresh,
  SubmitVerificationRequest,
  Verification,
  VerificationDraft,
  VerificationTier,
} from "@/types/verification";
import {
  CustomerDashboard,
  CustomerEvidence,
  VerificationListItem,
  VerificationTracking,
} from "@/types/tracking";

/**
 * Customer submission & payment API. Mirrors the backend controllers at
 * `app/domain/verification` and `app/domain/payment`. Backend is the single
 * source of truth for status, pricing and FX — the frontend never recomputes them.
 */
export class VerificationService {
  constructor(private readonly http: HttpClient) {}

  createDraft(idempotencyKey: string): Promise<SuccessResponse<VerificationDraft>> {
    return this.http.post(`/verifications/draft`, undefined, {
      headers: { "Idempotency-Key": idempotencyKey },
    });
  }

  saveDraft(id: string, step: number, payload: Record<string, unknown>): Promise<SuccessResponse<VerificationDraft>> {
    return this.http.put(`/verifications/${id}/draft`, { step, payload });
  }

  getDraft(id: string): Promise<SuccessResponse<VerificationDraft>> {
    return this.http.get(`/verifications/${id}/draft`);
  }

  getVerification(id: string): Promise<SuccessResponse<Verification>> {
    return this.http.get(`/verifications/${id}`);
  }

  // ── Tracking & evidence (§9) — the poll fallback (/tracking) shares one snapshot
  // shape with the /stream SSE endpoint. Backend owns every label and SLA state.

  listMine(page = 0, pageSize = 10): Promise<SuccessResponse<Page<VerificationListItem>>> {
    return this.http.get(`/verifications?page=${page}&pageSize=${pageSize}`);
  }

  /** Portal home summary (§9) — backend-derived counts + most-recent verifications. */
  getSummary(): Promise<SuccessResponse<CustomerDashboard>> {
    return this.http.get(`/verifications/summary`);
  }

  getTracking(id: string): Promise<SuccessResponse<VerificationTracking>> {
    return this.http.get(`/verifications/${id}/tracking`);
  }

  getEvidence(id: string, page = 0, pageSize = 10): Promise<SuccessResponse<Page<CustomerEvidence>>> {
    return this.http.get(`/verifications/${id}/evidence?page=${page}&pageSize=${pageSize}`);
  }

  /** SSE stream URL (§4.9). Consumed by EventSource in useVerificationStream. */
  streamUrl(id: string): string {
    return `/api/verifications/${id}/stream`;
  }

  quote(tier: VerificationTier, currency: TransactionCurrency): Promise<SuccessResponse<PriceQuote>> {
    return this.http.get(`/verifications/quote?tier=${tier}&currency=${currency}`);
  }

  geoAutocomplete(q: string): Promise<SuccessResponse<GeoSuggestion[]>> {
    return this.http.get(`/verifications/geo/autocomplete?q=${encodeURIComponent(q)}`);
  }

  geoPlace(placeId: string): Promise<SuccessResponse<GeoLocation | null>> {
    return this.http.get(`/verifications/geo/place/${placeId}`);
  }

  submit(id: string, payload: SubmitVerificationRequest): Promise<SuccessResponse<Verification>> {
    return this.http.post(`/verifications/${id}/submit`, payload);
  }

  /** Re-lock an expired price before payment (§17.1). priceChanged drives the interstitial. */
  refreshLock(id: string): Promise<SuccessResponse<PriceRefresh>> {
    return this.http.post(`/verifications/${id}/refresh-lock`);
  }

  initiatePayment(
    id: string,
    method: PaymentMethodKind,
    idempotencyKey: string,
  ): Promise<SuccessResponse<Payment>> {
    return this.http.post(`/payments/initiate/${id}`, { method }, {
      headers: { "Idempotency-Key": idempotencyKey },
    });
  }

  // Deterministic completion in local/test/dev (backend PAYMENT_STUB_MODE).
  stubConfirm(txRef: string, succeeded = true): Promise<SuccessResponse<{ processed: boolean }>> {
    return this.http.post(`/payments/stub/confirm`, { txRef, succeeded });
  }
}
