"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { httpClient } from "@/containers";
import { SystemConfigService } from "./system-config-service";
import { ConfigKey } from "@/types/systemConfig";

const service = new SystemConfigService(httpClient);

export const systemConfigKeys = { all: ["system-config"] as const };

export function useSystemConfigQuery() {
  return useQuery({
    queryKey: systemConfigKeys.all,
    queryFn: async () => (await service.list()).data ?? [],
  });
}

export function useSetSystemConfigMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { key: ConfigKey; value: number | string | boolean }) => service.set(v.key, v.value),
    onSuccess: (res) => {
      if (res.data) qc.setQueryData(systemConfigKeys.all, res.data);
    },
  });
}

export { service as systemConfigService };
