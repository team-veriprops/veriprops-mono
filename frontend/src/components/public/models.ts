export interface PublicVerificationSummary {
  vid: string;
  tier: string;
  propertyType: string;
  state: string;
  lga: string;
  status: string;
  trustBand: "HIGH" | "MED" | "LOW";
  reportDate: string | null;
  sharingMode: string;
}