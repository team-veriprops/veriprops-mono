"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { httpClient } from "@/containers";

export const trackingKeys = {
  tracking: (vid: string) => ["portal", "verifications", vid, "tracking"] as const,
  evidence: (vid: string) => ["portal", "verifications", vid, "evidence"] as const,
};

export function useVerificationTracking(vid: string) {
  return useQuery({
    queryKey: trackingKeys.tracking(vid),
    queryFn: () => httpClient.get(`/api/portal/verifications/${vid}/tracking`),
    staleTime: 15_000,
    refetchInterval: 60_000,  // S33 fallback poll
  });
}

export function useVerificationEvidence(vid: string) {
  return useQuery({
    queryKey: trackingKeys.evidence(vid),
    queryFn: () => httpClient.get(`/api/portal/verifications/${vid}/evidence`),
    staleTime: 30_000,
  });
}
