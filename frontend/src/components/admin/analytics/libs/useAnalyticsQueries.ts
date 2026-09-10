"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { httpClient } from "@/containers";
import { AnalyticsService } from "./analytics-service";

const service = new AnalyticsService(httpClient);

export const analyticsKeys = {
  funnel: () => ["analytics", "funnel"] as const,
  timeByTier: () => ["analytics", "time-by-tier"] as const,
  revenue: () => ["analytics", "revenue"] as const,
  regional: () => ["analytics", "regional"] as const,
  agentTrends: () => ["analytics", "agent-trends"] as const,
  whatsappChannel: (days?: number) => ["analytics", "whatsapp", days ?? "default"] as const,
};

export function useFunnelQuery() {
  return useQuery({ queryKey: analyticsKeys.funnel(), queryFn: async () => (await service.getFunnel()).data ?? null });
}
export function useTimeByTierQuery() {
  return useQuery({ queryKey: analyticsKeys.timeByTier(), queryFn: async () => (await service.getTimeByTier()).data ?? [] });
}
export function useRevenueQuery() {
  return useQuery({ queryKey: analyticsKeys.revenue(), queryFn: async () => (await service.getRevenue()).data ?? null });
}
export function useRegionalQuery() {
  return useQuery({ queryKey: analyticsKeys.regional(), queryFn: async () => (await service.getRegional()).data ?? [] });
}
export function useAgentTrendsQuery() {
  return useQuery({ queryKey: analyticsKeys.agentTrends(), queryFn: async () => (await service.getAgentTrends()).data ?? null });
}

export function useWhatsAppChannelAnalyticsQuery(days?: number) {
  return useQuery({
    queryKey: analyticsKeys.whatsappChannel(days),
    queryFn: async () => (await service.getWhatsAppChannel(days)).data ?? null,
  });
}

/**
 * Re-reads Meta's quality rating (§26.10, D81). The backend returns the whole panel, so the
 * cache is seeded from the response rather than invalidated — a second round trip would
 * re-run five aggregations to change one tile.
 */
export function useSyncWhatsAppQualityMutation(days?: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => (await service.syncWhatsAppQuality(days)).data ?? null,
    onSuccess: (data) => qc.setQueryData(analyticsKeys.whatsappChannel(days), data),
  });
}

export { service as analyticsService };
