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

export function useSetTierPricingMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ tier, priceNgnMinor, lineItems }: {
      tier: VerificationTier; priceNgnMinor: number; lineItems: LineItemInput[];
    }) => service.setTierPricing(tier, priceNgnMinor, lineItems),
    onSuccess: (res) => qc.setQueryData(pricingKeys.all(), res.data),
  });
}

export { service as pricingService };
