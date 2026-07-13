"use client";

import { useQuery } from "@tanstack/react-query";
import { DEFAULT_HISTORY_PAGE_SIZE } from "@lib/config/app";
import { httpClient } from "@/containers";
import { ConsentHistoryService } from "./consent-history-service";

const service = new ConsentHistoryService(httpClient);

export const consentHistoryKeys = {
  history: (page: number) => ["consent-history", page] as const,
};

export function useConsentHistoryQuery(page = 0) {
  return useQuery({
    queryKey: consentHistoryKeys.history(page),
    queryFn: async () => (await service.history(page, DEFAULT_HISTORY_PAGE_SIZE)).data ?? null,
  });
}

export { service as consentHistoryService };
