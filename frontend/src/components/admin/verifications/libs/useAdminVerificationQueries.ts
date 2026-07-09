"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { httpClient } from "@/containers";
import { AgentRole } from "@/types/agent";
import { AdminNoteCategory, VerificationListFilters } from "@/types/adminVerification";
import { AdminVerificationService } from "./admin-verification-service";

const service = new AdminVerificationService(httpClient);

export const adminVerificationKeys = {
  list: (filters: VerificationListFilters, page: number, pageSize: number) =>
    ["admin", "verifications", filters, page, pageSize] as const,
  detail: (id: string) => ["admin", "verifications", "detail", id] as const,
  summary: () => ["admin", "verifications", "summary"] as const,
};

/** Admin dashboard summary (§6) — backend-owned queue health rollups. */
export function useAdminDashboardQuery() {
  return useQuery({
    queryKey: adminVerificationKeys.summary(),
    queryFn: async () => (await service.getSummary()).data ?? null,
  });
}

export function useAdminVerificationsQuery(
  filters: VerificationListFilters,
  page = 0,
  pageSize = 10,
) {
  return useQuery({
    queryKey: adminVerificationKeys.list(filters, page, pageSize),
    queryFn: async () => (await service.list(filters, page, pageSize)).data ?? null,
    placeholderData: (prev) => prev,
  });
}

export function useAdminVerificationDetailQuery(verificationId: string) {
  return useQuery({
    queryKey: adminVerificationKeys.detail(verificationId),
    queryFn: async () => (await service.getDetail(verificationId)).data ?? null,
    enabled: !!verificationId,
  });
}

/** Every detail mutation returns the fresh detail; we seed the cache from the response. */
function useDetailMutation<TArgs = void>(
  fn: (args: TArgs) => Promise<{ data?: unknown }>,
  verificationId: string,
) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (res) => {
      if (res.data) qc.setQueryData(adminVerificationKeys.detail(verificationId), res.data);
      qc.invalidateQueries({ queryKey: ["admin", "verifications"] });
    },
  });
}

export function useAssignAgentMutation(verificationId: string) {
  return useDetailMutation(
    ({ role, agentId }: { role: AgentRole; agentId: string }) =>
      service.assign(verificationId, role, agentId),
    verificationId,
  );
}

export function usePauseMutation(verificationId: string) {
  return useDetailMutation<void>(() => service.pause(verificationId), verificationId);
}

export function useResumeMutation(verificationId: string) {
  return useDetailMutation<void>(() => service.resume(verificationId), verificationId);
}

export function useCancelMutation(verificationId: string) {
  return useDetailMutation(
    ({ reason }: { reason: string }) => service.cancel(verificationId, reason),
    verificationId,
  );
}

export function useSetDelayMutation(verificationId: string) {
  return useDetailMutation(
    ({ extraBusinessDays, reason }: { extraBusinessDays: number; reason?: string }) =>
      service.setDelay(verificationId, extraBusinessDays, reason),
    verificationId,
  );
}

export function useAddNoteMutation(verificationId: string) {
  return useDetailMutation(
    ({ category, body, pinned }: { category: AdminNoteCategory; body: string; pinned?: boolean }) =>
      service.addNote(verificationId, category, body, pinned),
    verificationId,
  );
}

export function useSubmitRebuttalMutation(verificationId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (chargebackId: string) => service.submitRebuttal(chargebackId),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: adminVerificationKeys.detail(verificationId) }),
  });
}

export function useResolveChargebackMutation(verificationId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ chargebackId, won }: { chargebackId: string; won: boolean }) =>
      service.resolveChargeback(chargebackId, won),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: adminVerificationKeys.detail(verificationId) }),
  });
}

export { service as adminVerificationService };
