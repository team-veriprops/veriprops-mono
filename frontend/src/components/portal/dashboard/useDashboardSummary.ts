"use client";

import { useQuery } from "@tanstack/react-query";
import { httpClient } from "@/containers";
import { DashboardService, DashboardSummary } from "./dashboard-service";

const dashboardService = new DashboardService(httpClient);

export const dashboardKeys = {
  summary: ["portal", "dashboard", "summary"] as const,
};

export function useDashboardSummary() {
  return useQuery<DashboardSummary>({
    queryKey: dashboardKeys.summary,
    queryFn: async (): Promise<DashboardSummary> => {
      const res = await dashboardService.fetchSummary();
      if (!res.data) throw new Error("No dashboard data");
      return res.data;
    },
    staleTime: 30_000,
  });
}
