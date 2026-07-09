"use client";

import { useQuery } from "@tanstack/react-query";
import { httpClient } from "@/containers";
import { AnalyticsService } from "./analytics-service";

const service = new AnalyticsService(httpClient);

export const analyticsKeys = {
  funnel: () => ["analytics", "funnel"] as const,
  timeByTier: () => ["analytics", "time-by-tier"] as const,
  revenue: () => ["analytics", "revenue"] as const,
  regional: () => ["analytics", "regional"] as const,
  agentTrends: () => ["analytics", "agent-trends"] as const,
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

export { service as analyticsService };
