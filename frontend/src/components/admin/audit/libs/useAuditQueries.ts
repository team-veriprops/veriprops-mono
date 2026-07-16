"use client";

import { useQuery } from "@tanstack/react-query";
import { DEFAULT_HISTORY_PAGE_SIZE } from "@lib/config/app";
import { httpClient } from "@/containers";
import { AuditService } from "./audit-service";

const service = new AuditService(httpClient);

export const auditKeys = {
  actions: (page: number, action?: string) => ["audit", "actions", page, action ?? "all"] as const,
};

export function useAdminActionsQuery(page = 0, actionType?: string) {
  return useQuery({
    queryKey: auditKeys.actions(page, actionType),
    queryFn: async () =>
      (await service.listAdminActions(actionType ? [actionType] : undefined, page, DEFAULT_HISTORY_PAGE_SIZE)).data ?? null,
  });
}

export { service as auditService };
