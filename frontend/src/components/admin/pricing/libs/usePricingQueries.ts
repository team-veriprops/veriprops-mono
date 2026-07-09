"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { httpClient } from "@/containers";
import { VerificationTier } from "@/types/verification";
import { LineItemInput } from "@/types/pricing";
import { PricingService } from "./pricing-service";

const service = new PricingService(httpClient);

export const pricingKeys = {
  all: () => ["pricing"] as const,
};

export function usePricingQuery() {
  return useQuery({
    queryKey: pricingKeys.all(),
    queryFn: async () => (await service.getPricing()).data ?? null,
  });
}

export function useSetTierPriceMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ tier, priceNgnMinor }: { tier: VerificationTier; priceNgnMinor: number }) =>
      service.setTierPrice(tier, priceNgnMinor),
    onSuccess: (res) => qc.setQueryData(pricingKeys.all(), res.data),
  });
}

export function useSetLineItemsMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ tier, lineItems }: { tier: VerificationTier; lineItems: LineItemInput[] }) =>
      service.setLineItems(tier, lineItems),
    onSuccess: (res) => qc.setQueryData(pricingKeys.all(), res.data),
  });
}

export { service as pricingService };
