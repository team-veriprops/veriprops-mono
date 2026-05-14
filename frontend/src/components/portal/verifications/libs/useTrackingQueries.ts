"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { httpClient } from "@/containers";
import type { ActivityPage } from "./verification-service";

export const trackingKeys = {
  tracking: (vid: string) => ["portal", "verifications", vid, "tracking"] as const,
  evidence: (vid: string) => ["portal", "verifications", vid, "evidence"] as const,
  activity: (vid: string, page: number) => ["portal", "verifications", vid, "activity", page] as const,
};

export function useVerificationTracking(vid: string) {
  return useQuery({
    queryKey: trackingKeys.tracking(vid),
    queryFn: () => httpClient.get(`/portal/verifications/${vid}/tracking`),
    staleTime: 15_000,
    refetchInterval: 60_000,  // S33 fallback poll
  });
}

export function useVerificationEvidence(vid: string) {
  return useQuery({
    queryKey: trackingKeys.evidence(vid),
    queryFn: () => httpClient.get(`/portal/verifications/${vid}/evidence`),
    staleTime: 30_000,
  });
}

export function useVerificationActivity(vid: string, page = 0) {
  return useQuery<{ data: ActivityPage }>({
    queryKey: trackingKeys.activity(vid, page),
    queryFn: () => httpClient.get(`/portal/verifications/${vid}/activity?page=${page}&page_size=20`),
    staleTime: 60_000,
  });
}
