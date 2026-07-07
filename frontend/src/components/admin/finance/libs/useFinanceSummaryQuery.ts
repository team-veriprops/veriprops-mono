"use client";

import { useQuery } from "@tanstack/react-query";
import { httpClient } from "@/containers";
import { FinanceSummaryService } from "./finance-summary-service";

const service = new FinanceSummaryService(httpClient);

export function useFinanceSummaryQuery() {
  return useQuery({
    queryKey: ["finance", "summary"],
    queryFn: async () => (await service.getSummary()).data ?? null,
  });
}

export { service as financeSummaryService };
