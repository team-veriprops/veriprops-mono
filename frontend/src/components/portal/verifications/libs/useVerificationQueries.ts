"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { httpClient } from "@/containers";
import {
  PaymentService,
  type PaymentMethod,
  type CustomerPayment,
} from "./payment-service";
import {
  VerificationService,
  type ConsentRecord,
  type Verification,
  type VerificationTier,
} from "./verification-service";
import { Page } from "@/types/models";

export const verificationService = new VerificationService(httpClient);
export const paymentService = new PaymentService(httpClient);

export const verificationKeys = {
  list: (page = 0, pageSize = 20) => ["verification", "list", page, pageSize] as const,
  activeDraft: ["verification", "active-draft"] as const,
  detail: (id: string) => ["verification", "detail", id] as const,
  pricing: (tier: VerificationTier, currency: string) =>
    ["verification", "pricing", tier, currency] as const,
  payment: (id: string) => ["payment", "detail", id] as const,
};

export function useVerificationList(page = 0, pageSize = 20) {
  return useQuery({
    queryKey: verificationKeys.list(page, pageSize),
    queryFn: async (): Promise<Page<Verification>> => (await verificationService.paginated(page, pageSize)),
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
    onSuccess: (data) => {
      // Set cache directly instead of invalidating — invalidating causes GET /verifications/me
      // to fire, which auto-creates a new DRAFT (create_or_resume_draft), replacing the
      // submitted verification in the wizard with an unrelated new draft.
      if (data.data) {
        qc.setQueryData(verificationKeys.activeDraft, data.data);
      }
      qc.invalidateQueries({ queryKey: verificationKeys.detail(id) });
    },
  });
}

export function useCancelVerificationMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => verificationService.cancel(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["verification", "list"] });
      qc.invalidateQueries({ queryKey: verificationKeys.activeDraft });
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

export function useMyPayments(page = 0, pageSize = 20) {
  return useQuery<Page<CustomerPayment>>({
    queryKey: ["payments", "my", page, pageSize],
    queryFn: async (): Promise<Page<CustomerPayment>> => {
      const res = await paymentService.listForCustomer(page, pageSize);
      if (!res.data) throw new Error("No payment data");
      return res.data;
    },
    staleTime: 30_000,
  });
}
