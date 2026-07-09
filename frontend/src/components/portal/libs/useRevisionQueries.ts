"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { httpClient } from "@/containers";
import { RevisionService } from "./revision-service";
import {
  DecideRecheckRequest,
  OpenDisputeRequest,
  RequestRecheckRequest,
  RequestUpgradeRequest,
  ResolveDisputeRequest,
} from "@/types/revision";

const service = new RevisionService(httpClient);

export const revisionKeys = {
  rechecks: (id: string) => ["rechecks", id] as const,
  upgrades: (id: string) => ["upgrades", id] as const,
  disputes: (id: string) => ["disputes", id] as const,
  pendingRechecks: (page: number) => ["admin-rechecks", page] as const,
  openDisputes: (page: number) => ["admin-disputes", page] as const,
  dispute: (id: string) => ["admin-dispute", id] as const,
};

// ── Customer ──────────────────────────────────────────────────────
export function useRechecksQuery(verificationId: string | null) {
  return useQuery({
    queryKey: revisionKeys.rechecks(verificationId ?? "none"),
    enabled: !!verificationId,
    queryFn: async () => (await service.listRechecks(verificationId as string)).data ?? [],
  });
}

export function useRequestRecheckMutation(verificationId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: RequestRecheckRequest) => service.requestRecheck(verificationId, req),
    onSuccess: () => qc.invalidateQueries({ queryKey: revisionKeys.rechecks(verificationId) }),
  });
}

export function useUpgradesQuery(verificationId: string | null) {
  return useQuery({
    queryKey: revisionKeys.upgrades(verificationId ?? "none"),
    enabled: !!verificationId,
    queryFn: async () => (await service.listUpgrades(verificationId as string)).data ?? [],
  });
}

export function useRequestUpgradeMutation(verificationId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: RequestUpgradeRequest) => service.requestUpgrade(verificationId, req),
    onSuccess: () => qc.invalidateQueries({ queryKey: revisionKeys.upgrades(verificationId) }),
  });
}

export function useDisputesQuery(verificationId: string | null) {
  return useQuery({
    queryKey: revisionKeys.disputes(verificationId ?? "none"),
    enabled: !!verificationId,
    queryFn: async () => (await service.listDisputes(verificationId as string)).data ?? [],
  });
}

export function useOpenDisputeMutation(verificationId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: OpenDisputeRequest) => service.openDispute(verificationId, req),
    onSuccess: () => qc.invalidateQueries({ queryKey: revisionKeys.disputes(verificationId) }),
  });
}

// ── Admin ─────────────────────────────────────────────────────────
export function usePendingRechecksQuery(page = 0, pageSize = 10) {
  return useQuery({
    queryKey: revisionKeys.pendingRechecks(page),
    queryFn: async () => (await service.listPendingRechecks(page, pageSize)).data ?? null,
  });
}

export function useDecideRecheckMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { recheckId: string; req: DecideRecheckRequest }) =>
      service.decideRecheck(v.recheckId, v.req),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-rechecks"] }),
  });
}

export function useOpenDisputesQuery(page = 0, pageSize = 10) {
  return useQuery({
    queryKey: revisionKeys.openDisputes(page),
    queryFn: async () => (await service.listOpenDisputes(page, pageSize)).data ?? null,
  });
}

export function useDisputeQuery(disputeId: string | null) {
  return useQuery({
    queryKey: revisionKeys.dispute(disputeId ?? "none"),
    enabled: !!disputeId,
    queryFn: async () => (await service.getDispute(disputeId as string)).data ?? null,
  });
}

export function useResolveDisputeMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { disputeId: string; req: ResolveDisputeRequest }) =>
      service.resolveDispute(v.disputeId, v.req),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-disputes"] }),
  });
}

// ── Agent defence ─────────────────────────────────────────────────
export function useAgentDisputesQuery() {
  return useQuery({
    queryKey: ["agent-disputes"],
    queryFn: async () => (await service.listAgentDisputes()).data ?? [],
  });
}

export function useSubmitDefenceMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { disputeId: string; text: string }) => service.submitDefence(v.disputeId, v.text),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["agent-disputes"] }),
  });
}

export { service as revisionService };
