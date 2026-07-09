"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { httpClient } from "@/containers";
import { BroadcastAudience, ComposeBroadcastRequest } from "@/types/broadcast";
import { BroadcastService } from "./broadcast-service";

const service = new BroadcastService(httpClient);

export const broadcastKeys = {
  list: (page: number, status?: string) => ["broadcast", "list", page, status ?? "all"] as const,
  detail: (id: string) => ["broadcast", id] as const,
  preview: (audience: BroadcastAudience) => ["broadcast", "preview", audience] as const,
};

export function useBroadcastsQuery(page = 0, status?: string) {
  return useQuery({
    queryKey: broadcastKeys.list(page, status),
    queryFn: async () => (await service.list(page, 10, status)).data ?? null,
  });
}

export function useBroadcastQuery(id: string | null) {
  return useQuery({
    queryKey: broadcastKeys.detail(id ?? "none"),
    enabled: !!id,
    queryFn: async () => (await service.get(id as string)).data ?? null,
  });
}

export function useBroadcastPreviewQuery(audience: BroadcastAudience) {
  return useQuery({
    queryKey: broadcastKeys.preview(audience),
    queryFn: async () => (await service.preview(audience)).data ?? null,
  });
}

export function useComposeBroadcastMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: ComposeBroadcastRequest) => service.compose(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["broadcast", "list"] }),
  });
}

export function useSendBroadcastMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => service.send(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["broadcast"] }),
  });
}

export function useCancelBroadcastMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => service.cancel(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["broadcast"] }),
  });
}

export { service as broadcastService };
