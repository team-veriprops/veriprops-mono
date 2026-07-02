"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { httpClient } from "@/containers";
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
  quote: (tier: VerificationTier, currency: TransactionCurrency) =>
    ["verification", "quote", tier, currency] as const,
};

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

export function useQuoteQuery(tier: VerificationTier, currency: TransactionCurrency, enabled = true) {
  return useQuery({
    queryKey: verificationKeys.quote(tier, currency),
    enabled,
    queryFn: async () => (await service.quote(tier, currency)).data ?? null,
    staleTime: 5 * 60_000,
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
    staleTime: 5 * 60_000,
  });
}

export { service as verificationService };
