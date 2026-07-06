"use client";

import { useQuery } from "@tanstack/react-query";
import { httpClient } from "@/containers";
import { ReferralService } from "./referral-service";

const service = new ReferralService(httpClient);

export const referralKeys = {
  mine: () => ["referral", "mine"] as const,
};

/** The signed-in customer's referral link + credit balances (§17.1). */
export function useReferralSummaryQuery() {
  return useQuery({
    queryKey: referralKeys.mine(),
    queryFn: async () => (await service.getMine()).data ?? null,
  });
}

export { service as referralService };
