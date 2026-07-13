"use client";

import { useCallback } from "react";
import { DEFAULT_PAGE_SIZE, REFETCH_INTERVAL_MS } from "@lib/config/app";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { httpClient } from "@/containers";
import { useUserStream } from "@lib/useUserStream";
import { EarningsService } from "./earnings-service";

const service = new EarningsService(httpClient);

export const earningsKeys = {
  summary: () => ["earnings", "summary"] as const,
  jobs: (page: number) => ["earnings", "jobs", page] as const,
};

export function useEarningsSummaryQuery() {
  return useQuery({
    queryKey: earningsKeys.summary(),
    queryFn: async () => (await service.getSummary()).data ?? null,
    refetchInterval: REFETCH_INTERVAL_MS,
  });
}

export function useEarningJobsQuery(page = 0, pageSize = DEFAULT_PAGE_SIZE) {
  return useQuery({
    queryKey: earningsKeys.jobs(page),
    queryFn: async () => (await service.listJobs(page, pageSize)).data ?? null,
  });
}

/** Live "money moved to available" refresh — a COMMISSION_CLEARED notification push
 * invalidates the earnings figures (§15.1). Mirrors useNotificationRealtime. */
export function useEarningsRealtime(enabled = true) {
  const qc = useQueryClient();
  const onEvent = useCallback(
    (evt: { event: string }) => {
      if (evt.event === "notification" || evt.event === "notification_unread") {
        qc.invalidateQueries({ queryKey: ["earnings"] });
      }
    },
    [qc],
  );
  useUserStream({ onEvent, enabled });
}

export { service as earningsService };
