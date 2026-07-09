"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { httpClient } from "@/containers";
import { ReportService } from "./report-service";

const service = new ReportService(httpClient);

export const reportKeys = {
  detail: (id: string) => ["report", id] as const,
};

export function useReportQuery(id: string | null) {
  return useQuery({
    queryKey: reportKeys.detail(id ?? "none"),
    enabled: !!id,
    queryFn: async () => (await service.getReport(id as string)).data ?? null,
  });
}

export function useAcknowledgeReportMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => service.acknowledge(id),
    onSuccess: (res, id) => {
      if (res.data) qc.setQueryData(reportKeys.detail(id), res.data);
    },
  });
}

export { service as reportService };
