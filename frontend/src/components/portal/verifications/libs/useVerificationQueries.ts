"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { httpClient } from "@/containers";
import {
  PaymentService,
  type PaymentMethod,
} from "./payment-service";
import {
  VerificationService,
  type ConsentRecord,
  type Verification,
  type VerificationTier,
} from "./verification-service";

export const verificationService = new VerificationService(httpClient);
export const paymentService = new PaymentService(httpClient);

export const verificationKeys = {
  list: ["verification", "list"] as const,
  activeDraft: ["verification", "active-draft"] as const,
  detail: (id: string) => ["verification", "detail", id] as const,
  pricing: (tier: VerificationTier, currency: string) =>
    ["verification", "pricing", tier, currency] as const,
  payment: (id: string) => ["payment", "detail", id] as const,
};

export function useVerificationList() {
  return useQuery({
    queryKey: verificationKeys.list,
    queryFn: async (): Promise<Verification[]> => (await verificationService.list()).data ?? [],
    staleTime: 30_000,
  });
}

export function useActiveDraft(enabled = true) {
  return useQuery({
    queryKey: verificationKeys.activeDraft,
    enabled,
    queryFn: async () => (await verificationService.getActiveDraft()).data ?? null,
    staleTime: 10_000,
  });
}

export function useVerification(id: string, enabled = true) {
  return useQuery({
    queryKey: verificationKeys.detail(id),
    enabled: enabled && !!id,
    queryFn: async () => (await verificationService.get(id)).data ?? null,
    staleTime: 5_000,
  });
}

export function usePricingQuote(tier: VerificationTier, currency: string) {
  return useQuery({
    queryKey: verificationKeys.pricing(tier, currency),
    queryFn: async () => (await verificationService.quote(tier, currency)).data ?? null,
    staleTime: 60_000,
  });
}

export function useSaveDraftMutation(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { step: number; payload: Record<string, unknown> }) =>
      verificationService.saveDraftStep(id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: verificationKeys.activeDraft });
      qc.invalidateQueries({ queryKey: verificationKeys.detail(id) });
    },
  });
}

export function useSelectTierMutation(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { tier: VerificationTier; currency: string }) =>
      verificationService.selectTier(id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: verificationKeys.activeDraft });
      qc.invalidateQueries({ queryKey: verificationKeys.detail(id) });
    },
  });
}

export function useSubmitVerificationMutation(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (consents: ConsentRecord[]) =>
      verificationService.submit(id, { consents }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: verificationKeys.activeDraft });
      qc.invalidateQueries({ queryKey: verificationKeys.detail(id) });
    },
  });
}

export function useInitiatePaymentMutation() {
  return useMutation({
    mutationFn: (payload: {
      verificationId: string;
      method: PaymentMethod;
      redirectUrl?: string;
    }) => paymentService.initiate(payload),
  });
}

export function usePayment(id: string, enabled = true) {
  return useQuery({
    queryKey: verificationKeys.payment(id),
    enabled: enabled && !!id,
    queryFn: async () => (await paymentService.get(id)).data ?? null,
    staleTime: 5_000,
    refetchInterval: 5_000,
  });
}
