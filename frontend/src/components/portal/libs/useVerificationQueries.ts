"use client";

import { useCallback } from "react";
import { DEFAULT_HISTORY_PAGE_SIZE, REFETCH_INTERVAL_MS, LONG_STALE_TIME_MS } from "@lib/config/app";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { httpClient } from "@/containers";
import { useVerificationStream } from "@lib/useVerificationStream";
import { TransactionCurrency } from "@/types/models";
import {
  PaymentMethodKind,
  SubmitVerificationRequest,
  VerificationTier,
} from "@/types/verification";
import { VerificationService } from "./verification-service";

const service = new VerificationService(httpClient);

export const verificationKeys = {
  detail: (id: string) => ["verification", id] as const,
  draft: (id: string) => ["verification", id, "draft"] as const,
  list: (page: number) => ["verification", "list", page] as const,
  summary: () => ["verification", "summary"] as const,
  tracking: (id: string) => ["verification", id, "tracking"] as const,
  evidence: (id: string, page: number) => ["verification", id, "evidence", page] as const,
  activity: (id: string, page: number) => ["verification", id, "activity", page] as const,
  quote: (tier: VerificationTier, currency: TransactionCurrency) =>
    ["verification", "quote", tier, currency] as const,
};

/** Customer verification activity log (§19.2) — PII-safe transition history. */
export function useVerificationActivityQuery(id: string, page = 0) {
  return useQuery({
    queryKey: verificationKeys.activity(id, page),
    queryFn: async () => (await service.getActivity(id, page, DEFAULT_HISTORY_PAGE_SIZE)).data ?? null,
  });
}

/** Portal dashboard summary (§9) — backend-owned rollups over the customer's work. */
export function useCustomerDashboardQuery() {
  return useQuery({
    queryKey: verificationKeys.summary(),
    queryFn: async () => (await service.getSummary()).data ?? null,
  });
}

export function useCreateDraftMutation() {
  return useMutation({
    mutationFn: (idempotencyKey: string) => service.createDraft(idempotencyKey),
  });
}

export function useSaveDraftMutation() {
  return useMutation({
    mutationFn: ({ id, step, payload }: { id: string; step: number; payload: Record<string, unknown> }) =>
      service.saveDraft(id, step, payload),
  });
}

export function useVerificationQuery(id: string | null) {
  return useQuery({
    queryKey: verificationKeys.detail(id ?? "none"),
    enabled: !!id,
    queryFn: async () => (await service.getVerification(id as string)).data ?? null,
  });
}

/** The customer's own verifications list (§9). */
export function useMyVerificationsQuery(page = 0) {
  return useQuery({
    queryKey: verificationKeys.list(page),
    queryFn: async () => (await service.listMine(page)).data ?? null,
  });
}

/**
 * Live tracking snapshot (§9.1) with the mandated real-time behaviour (§4.9):
 * a 60-second polling fallback (`refetchInterval`) plus an SSE subscription that
 * refetches the *same* snapshot on any pushed event. Poll is the source of truth;
 * SSE only reduces latency, so a dropped push never leaves the UI stale.
 */
export function useVerificationTracking(id: string | null, enabled = true) {
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: verificationKeys.tracking(id ?? "none"),
    enabled: !!id && enabled,
    queryFn: async () => (await service.getTracking(id as string)).data ?? null,
    refetchInterval: REFETCH_INTERVAL_MS, // polling fallback — shares the snapshot shape
  });

  const onEvent = useCallback(() => {
    if (id) qc.invalidateQueries({ queryKey: verificationKeys.tracking(id) });
  }, [id, qc]);

  useVerificationStream({ vid: id ?? "", onEvent, enabled: !!id && enabled });
  return query;
}

export function useEvidenceQuery(id: string | null, page = 0, enabled = true) {
  return useQuery({
    queryKey: verificationKeys.evidence(id ?? "none", page),
    enabled: !!id && enabled,
    queryFn: async () => (await service.getEvidence(id as string, page)).data ?? null,
  });
}

export function useQuoteQuery(tier: VerificationTier, currency: TransactionCurrency, enabled = true) {
  return useQuery({
    queryKey: verificationKeys.quote(tier, currency),
    enabled,
    queryFn: async () => (await service.quote(tier, currency)).data ?? null,
    staleTime: LONG_STALE_TIME_MS,
  });
}

export function useGeoAutocompleteQuery(q: string) {
  return useQuery({
    queryKey: ["verification", "geo", q],
    enabled: q.trim().length >= 2,
    queryFn: async () => (await service.geoAutocomplete(q)).data ?? [],
  });
}

export function useSubmitVerificationMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: SubmitVerificationRequest }) =>
      service.submit(id, payload),
    onSuccess: (_res, vars) => qc.invalidateQueries({ queryKey: verificationKeys.detail(vars.id) }),
  });
}

/** Re-lock an expired price before payment (§17.1). Result.priceChanged gates the interstitial. */
export function useRefreshLockMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => service.refreshLock(id),
    onSuccess: (_res, id) => qc.invalidateQueries({ queryKey: verificationKeys.detail(id) }),
  });
}

export function useInitiatePaymentMutation() {
  return useMutation({
    mutationFn: ({ id, method, idempotencyKey }: { id: string; method: PaymentMethodKind; idempotencyKey: string }) =>
      service.initiatePayment(id, method, idempotencyKey),
  });
}

export function useStubConfirmMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ txRef, succeeded }: { txRef: string; succeeded?: boolean }) =>
      service.stubConfirm(txRef, succeeded),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["verification"] }),
  });
}

/** Current VERIFICATION_TERMS version — backend is the source of truth (PRD §5.3). */
export function useVerificationTermsQuery() {
  return useQuery({
    queryKey: ["verification", "terms"],
    queryFn: async () => {
      const res = await httpClient.get<{ data?: { consentVersion: string } }>(
        "/users/auth/consents/documents/verification-terms",
      );
      return res.data ?? null;
    },
    staleTime: LONG_STALE_TIME_MS,
  });
}

export { service as verificationService };
