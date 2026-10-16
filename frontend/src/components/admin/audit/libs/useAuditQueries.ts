"use client";

import { useQuery } from "@tanstack/react-query";
import { httpClient } from "@/containers";
import { AuditService } from "./audit-service";

const service = new AuditService(httpClient);

export const auditKeys = {
  actions: (page: number, pageSize: number, action?: string, orderBy?: string) =>
    ["audit", "actions", page, pageSize, action ?? "all", orderBy ?? ""] as const,
};

export function useAdminActionsQuery(page: number, pageSize: number, actionType?: string, orderBy?: string) {
  return useQuery({
    queryKey: auditKeys.actions(page, pageSize, actionType, orderBy),
    queryFn: async () =>
      (await service.listAdminActions(actionType ? [actionType] : undefined, page, pageSize, orderBy)).data ?? null,
    placeholderData: (prev) => prev,
  });
}

export { service as auditService };
