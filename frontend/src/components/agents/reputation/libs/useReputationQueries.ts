"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { httpClient } from "@/containers";
import { AvailabilityStatus, CoverageArea } from "@/types/agentReputation";
import { AgentRole } from "@/types/agent";
import { ReputationService } from "./reputation-service";

const service = new ReputationService(httpClient);

export const reputationKeys = {
  metrics: () => ["agent-metrics"] as const,
  profile: () => ["agent-profile"] as const,
  coverage: () => ["agent-coverage"] as const,
  locations: () => ["nigeria-locations"] as const,
  suggested: (vid: string, role: string) => ["suggested-agents", vid, role] as const,
};

export function useAgentMetricsQuery() {
  return useQuery({
    queryKey: reputationKeys.metrics(),
    queryFn: async () => (await service.getMetrics()).data ?? null,
  });
}

export function useAgentProfileQuery() {
  return useQuery({
    queryKey: reputationKeys.profile(),
    queryFn: async () => (await service.getProfile()).data ?? null,
  });
}

export function useSetAvailabilityMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (availability: AvailabilityStatus) => service.setAvailability(availability),
    onSuccess: () => qc.invalidateQueries({ queryKey: reputationKeys.profile() }),
  });
}

export function useCoverageQuery() {
  return useQuery({
    queryKey: reputationKeys.coverage(),
    queryFn: async () => (await service.getCoverage()).data ?? [],
  });
}

export function useNigeriaLocationsQuery() {
  return useQuery({
    queryKey: reputationKeys.locations(),
    queryFn: async () => (await service.getNigeriaLocations()).data?.states ?? [],
    staleTime: Infinity, // reference data
  });
}

export function useSetCoverageMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (areas: CoverageArea[]) => service.setCoverage(areas),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: reputationKeys.coverage() });
      qc.invalidateQueries({ queryKey: reputationKeys.profile() });
    },
  });
}

export function useSuggestedAgentsQuery(verificationId: string | null, role: AgentRole | null) {
  return useQuery({
    queryKey: reputationKeys.suggested(verificationId ?? "none", role ?? "none"),
    enabled: !!verificationId && !!role,
    queryFn: async () =>
      (await service.getSuggestedAgents(verificationId as string, role as AgentRole)).data ?? [],
  });
}

export { service as reputationService };
