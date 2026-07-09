import { HttpClient } from "@lib/FetchHttpClient";
import { SuccessResponse } from "@/types/models";
import { FinanceSummary } from "@/types/finance";

/**
 * Finance summary API (PRD §18.1). Mirrors app/domain/finance/controller.py — the Finance
 * landing tiles (revenue + payment/commission/payout counts). Backend-derived.
 */
export class FinanceSummaryService {
  constructor(private readonly http: HttpClient) {}

  getSummary(): Promise<SuccessResponse<FinanceSummary>> {
    return this.http.get(`/admin/finance/summary`);
  }
}
