"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { httpClient } from "@/containers";
import { ShareService } from "./share-service";
import { CreateShareRequest } from "@/types/share";

const service = new ShareService(httpClient);

export const shareKeys = {
  list: (verificationId: string) => ["shares", verificationId] as const,
  shared: (token: string) => ["shared", token] as const,
};

export function useSharesQuery(verificationId: string | null) {
  return useQuery({
    queryKey: shareKeys.list(verificationId ?? "none"),
    enabled: !!verificationId,
    queryFn: async () => (await service.listShares(verificationId as string)).data ?? [],
  });
}

export function useCreateShareMutation(verificationId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: CreateShareRequest) => service.createShare(verificationId, req),
    onSuccess: () => qc.invalidateQueries({ queryKey: shareKeys.list(verificationId) }),
  });
}

export function useRevokeShareMutation(verificationId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (shareId: string) => service.revokeShare(verificationId, shareId),
    onSuccess: () => qc.invalidateQueries({ queryKey: shareKeys.list(verificationId) }),
  });
}

export function useSetPublicVisibilityMutation(verificationId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (enabled: boolean) => service.setPublicVisibility(verificationId, enabled),
    onSuccess: () => qc.invalidateQueries({ queryKey: shareKeys.list(verificationId) }),
  });
}

// ── Public (unauthenticated) share resolution ────────────────────

export function useSharedReportQuery(token: string | null) {
  return useQuery({
    queryKey: shareKeys.shared(token ?? "none"),
    enabled: !!token,
    queryFn: async () => (await service.resolveShared(token as string)).data ?? null,
  });
}

export function useAcknowledgeSharedMutation(token: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => service.acknowledgeShared(token),
    onSuccess: (res) => {
      if (res.data) qc.setQueryData(shareKeys.shared(token), res.data);
    },
  });
}

export { service as shareService };
