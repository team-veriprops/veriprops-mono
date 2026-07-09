// Pricing config types — mirror backend camelCase DTOs (PRD §18.1, D36).
import { VerificationTier } from "@/types/verification";

export interface PricingLineItem {
  id: string;
  tier: string;
  label: string;
  amountMinor: number;
  sortOrder: number;
  dateCreated: string;
}

export interface PricingTier {
  tier: VerificationTier;
  priceNgnMinor: number;
  lineItems: PricingLineItem[];
}

export interface UpgradeDelta {
  fromTier: VerificationTier;
  toTier: VerificationTier;
  deltaMinor: number;
}

export interface TierPricingView {
  tiers: PricingTier[];
  upgradeDeltas: UpgradeDelta[];
}

export interface LineItemInput {
  label: string;
  amountMinor: number;
}
