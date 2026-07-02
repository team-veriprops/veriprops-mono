// Verification submission & payment types — mirror backend camelCase DTOs
// (PRD §5, §4.4). Backend is the single source of truth for status, pricing, and FX.
import { TransactionCurrency } from "@/types/models";

export enum VerificationStatus {
  DRAFT = "DRAFT",
  SUBMITTED = "SUBMITTED",
  PAYMENT_PENDING = "PAYMENT_PENDING",
  PAID = "PAID",
  IN_PROGRESS = "IN_PROGRESS",
  UNDER_REVIEW = "UNDER_REVIEW",
  COMPLETED = "COMPLETED",
  DISPUTED = "DISPUTED",
  CANCELLED = "CANCELLED",
  REFUNDED = "REFUNDED",
  FAILED = "FAILED",
}

export enum VerificationTier {
  BASIC = "BASIC",
  STANDARD = "STANDARD",
  PREMIUM = "PREMIUM",
}

export enum PropertyKind {
  LAND = "LAND",
  BUILDING = "BUILDING",
}

export enum PaymentMethodKind {
  CARD = "CARD",
  BANK_TRANSFER = "BANK_TRANSFER",
}

export enum PaymentStatus {
  INITIATED = "INITIATED",
  PROCESSING = "PROCESSING",
  SUCCEEDED = "SUCCEEDED",
  FAILED = "FAILED",
  PENDING_TRANSFER = "PENDING_TRANSFER",
}

export interface SellerInfo {
  name?: string;
  phone?: string;
  email?: string;
  relationship?: string;
  notes?: string;
}

export interface PropertyInput {
  propertyType: PropertyKind;
  address?: string;
  landmark?: string;
  state?: string;
  lga?: string;
  latitude?: number;
  longitude?: number;
  placeId?: string;
  details?: Record<string, unknown>;
  seller?: SellerInfo;
  documents?: Record<string, unknown>[];
}

export interface GeoSuggestion {
  placeId: string;
  description: string;
}

export interface GeoLocation {
  placeId?: string;
  address: string;
  state?: string;
  lga?: string;
  latitude: number;
  longitude: number;
}

export interface PriceQuote {
  tier: VerificationTier;
  priceNgnMinor: number;
  currency: TransactionCurrency;
  chargeAmountMinor: number;
  fxRate: number;
}

export interface SubmitVerificationRequest {
  property: PropertyInput;
  tier: VerificationTier;
  currency: TransactionCurrency;
  consent: { consentVersion: string };
}

export interface Verification {
  id: string;
  vid: string;
  status: VerificationStatus;
  tier?: VerificationTier;
  propertyId?: string;
  priceLockedMinor?: number;
  currency: TransactionCurrency;
  chargeCurrency?: TransactionCurrency;
  chargeAmountMinor?: number;
  fxRateAtQuote?: number;
  priceLockExpiresAt?: string;
  paidAt?: string;
  slaDueDate?: string;
  draftStep: number;
}

export interface VerificationDraft {
  id: string;
  vid: string;
  status: VerificationStatus;
  step: number;
  payload: Record<string, unknown>;
}

export interface Payment {
  id: string;
  verificationId: string;
  txRef: string;
  method: PaymentMethodKind;
  status: PaymentStatus;
  amountMinor: number;
  currency: TransactionCurrency;
  chargeCurrency?: TransactionCurrency;
  chargeAmountMinor?: number;
  checkoutUrl?: string;
  dateCreated: string;
}
