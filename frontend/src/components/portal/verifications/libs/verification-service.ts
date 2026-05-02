import { HttpClient } from "@lib/FetchHttpClient";
import { SuccessResponse } from "@/types/models";

export type VerificationTier = "BASIC" | "STANDARD" | "PREMIUM";
export type VerificationStatus =
  | "DRAFT"
  | "SUBMITTED"
  | "PAYMENT_PENDING"
  | "PAID"
  | "IN_PROGRESS"
  | "UNDER_REVIEW"
  | "COMPLETED"
  | "DISPUTED"
  | "CANCELLED"
  | "REFUNDED"
  | "FAILED";

export type PropertyType = "LAND" | "BUILDING";

export interface PricingLineItem {
  label: string;
  amountMinor: number;
  description?: string | null;
}

export interface PricingSnapshot {
  tier: VerificationTier;
  currency: string;
  baseAmountMinor: number;
  lineItems: PricingLineItem[];
  totalAmountMinor: number;
  fxRate: number | null;
  fxSourceCurrency: string;
  fxFetchedAt: string | null;
  fxStale: boolean;
  lockedAt: string | null;
  lockedUntil: string | null;
}

export interface PropertyDto {
  id: string;
  source: "MANUAL" | "LISTING_URL";
  propertyType: PropertyType;
  state: string;
  lga: string | null;
  addressLine: string | null;
  lat: number | null;
  lng: number | null;
  landmarkDescription: string | null;
  details: Record<string, unknown> | null;
  documents: string[];
  sellerInfo: Record<string, unknown> | null;
}

export interface Verification {
  id: string;
  vid: string;
  customerId: string;
  tier: VerificationTier;
  status: VerificationStatus;
  property: PropertyDto | null;
  pricing: PricingSnapshot | null;
  submittedAt: string | null;
  paidAt: string | null;
  completedAt: string | null;
  createdAt: string;
  updatedAt: string | null;
  draftStep: number;
  draftPayload: Record<string, unknown> | null;
}

export interface ConsentRecord {
  documentType: string;
  consentVersion: string;
}

export class VerificationService {
  private readonly base = "/verifications";

  constructor(private readonly http: HttpClient) {}

  getActiveDraft(): Promise<SuccessResponse<Verification>> {
    return this.http.get(`${this.base}/me`);
  }

  get(id: string): Promise<SuccessResponse<Verification>> {
    return this.http.get(`${this.base}/${id}`);
  }

  saveDraftStep(
    id: string,
    payload: { step: number; payload: Record<string, unknown> },
  ): Promise<SuccessResponse<Verification>> {
    return this.http.post(`${this.base}/${id}/draft`, payload);
  }

  selectTier(
    id: string,
    payload: { tier: VerificationTier; currency: string },
  ): Promise<SuccessResponse<Verification>> {
    return this.http.post(`${this.base}/${id}/tier`, payload);
  }

  submit(
    id: string,
    payload: { consents: ConsentRecord[] },
  ): Promise<SuccessResponse<Verification>> {
    return this.http.post(`${this.base}/${id}/submit`, payload);
  }

  list(): Promise<SuccessResponse<Verification[]>> {
    return this.http.get(`${this.base}/me/list`);
  }

  quote(
    tier: VerificationTier,
    currency: string,
  ): Promise<SuccessResponse<PricingSnapshot>> {
    return this.http.get(
      `${this.base}/pricing/quote?tier=${tier}&currency=${currency}`,
    );
  }
}
