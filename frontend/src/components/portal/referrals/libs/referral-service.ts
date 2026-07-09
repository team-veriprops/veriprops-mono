import { HttpClient } from "@lib/FetchHttpClient";
import { SuccessResponse } from "@/types/models";
import { ReferralSummary } from "@/types/referral";

/**
 * Referral API (PRD §17.1). Mirrors the backend controller at
 * app/domain/referral/controller.py — the link, credit balances, and eligibility are
 * all backend-owned; the frontend renders what it receives.
 */
export class ReferralService {
  constructor(private readonly http: HttpClient) {}

  getMine(): Promise<SuccessResponse<ReferralSummary>> {
    return this.http.get(`/referrals/me`);
  }
}
