"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { httpClient } from "@/containers";
import { ErasureService } from "./erasure-service";

const service = new ErasureService(httpClient);

export const erasureKeys = {
  mine: ["erasure", "mine"] as const,
  adminList: (page: number, status?: string) => ["erasure", "admin", page, status ?? "all"] as const,
};

// ── Self-service ──
export function useMyErasureRequestsQuery() {
  return useQuery({
    queryKey: erasureKeys.mine,
    queryFn: async () => (await service.listMine()).data ?? [],
  });
}

export function useRequestErasureMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (reason?: string) => service.requestMine(reason),
    onSuccess: () => qc.invalidateQueries({ queryKey: erasureKeys.mine }),
  });
}

// ── Admin review ──
export function useAdminErasureRequestsQuery(page = 0, status?: string) {
  return useQuery({
    queryKey: erasureKeys.adminList(page, status),
    queryFn: async () => (await service.list(status, page, 10)).data ?? null,
  });
}

export function useApproveErasureMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => service.approve(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["erasure", "admin"] }),
  });
}

export function useRejectErasureMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, note }: { id: string; note?: string }) => service.reject(id, note),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["erasure", "admin"] }),
  });
}

export function useExecuteErasureMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => service.execute(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["erasure", "admin"] }),
  });
}

export { service as erasureService };
