"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { httpClient } from "@/containers";
import { AuthorizeCaseDelegate } from "@/types/delegate";
import { DelegateService } from "./delegate-service";

const service = new DelegateService(httpClient);

export const delegateKeys = {
  forCase: (verificationId: string) => ["delegates", verificationId] as const,
};

export function useDelegatesQuery(verificationId: string) {
  return useQuery({
    queryKey: delegateKeys.forCase(verificationId),
    queryFn: async () => (await service.list(verificationId)).data ?? [],
  });
}

export function useAuthorizeDelegateMutation(verificationId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (delegate: AuthorizeCaseDelegate) =>
      (await service.authorize(verificationId, delegate)).data ?? null,
    // The row exists the moment it is authorized, unverified — the page has to show that
    // state, or a buyer who never relays the code sees nothing and nominates again.
    onSuccess: () => qc.invalidateQueries({ queryKey: delegateKeys.forCase(verificationId) }),
  });
}

export function useConfirmDelegateMutation(verificationId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (code: string) =>
      (await service.confirm(verificationId, code)).data ?? null,
    onSuccess: () => qc.invalidateQueries({ queryKey: delegateKeys.forCase(verificationId) }),
  });
}

export function useRevokeDelegateMutation(verificationId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => (await service.revoke(verificationId)).data ?? null,
    onSuccess: () => qc.invalidateQueries({ queryKey: delegateKeys.forCase(verificationId) }),
  });
}

export { service as delegateService };
