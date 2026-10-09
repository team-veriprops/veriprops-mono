import { HttpClient } from "@lib/FetchHttpClient";
import { SuccessResponse } from "@/types/models";
import { VerificationTier } from "@/types/verification";
import { LineItemInput, TierPricingView } from "@/types/pricing";

/**
 * Pricing config API (PRD §18.1, D36). Mirrors the backend controller at
 * app/domain/verification/pricing_config/controller.py. Edits take effect on the next
 * quote — the Phase-18 exit criterion (no deploy). Backend is the source of truth.
 */
export class PricingService {
  constructor(private readonly http: HttpClient) {}

  getPricing(): Promise<SuccessResponse<TierPricingView>> {
    return this.http.get(`/admin/pricing`);
  }

  /** A tier's price and its itemised breakdown, saved together; the items must add up to the
   *  price (an empty list leaves the tier without a breakdown). */
  setTierPricing(
    tier: VerificationTier, priceNgnMinor: number, lineItems: LineItemInput[],
  ): Promise<SuccessResponse<TierPricingView>> {
    return this.http.put(`/admin/pricing/tiers/${tier}`, { priceNgnMinor, lineItems });
  }
}
