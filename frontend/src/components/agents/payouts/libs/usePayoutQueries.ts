"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { DEFAULT_PAGE_SIZE } from "@lib/config/app";
import { httpClient } from "@/containers";
import {
  AddBankAccountRequest,
  QuotePayoutRequest,
  RequestPayoutRequest,
  ResolveBankAccountRequest,
} from "@/types/payout";
import { PayoutService } from "./payout-service";

const service = new PayoutService(httpClient);

export const payoutKeys = {
  list: (page: number) => ["payouts", page] as const,
  bankAccounts: () => ["payout-bank-accounts"] as const,
  banks: () => ["payout-banks"] as const,
};

export function usePayoutsQuery(page = 0, pageSize = DEFAULT_PAGE_SIZE) {
  return useQuery({
    queryKey: payoutKeys.list(page),
    queryFn: async () => (await service.listPayouts(page, pageSize)).data ?? null,
  });
}

export function useBankAccountsQuery() {
  return useQuery({
    queryKey: payoutKeys.bankAccounts(),
    queryFn: async () => (await service.listBankAccounts()).data ?? [],
  });
}

/** The paying gateway's bank list. It changes rarely, so it is kept for the session. */
export function useBanksQuery() {
  return useQuery({
    queryKey: payoutKeys.banks(),
    queryFn: async () => (await service.listBanks()).data ?? [],
    staleTime: Infinity,
  });
}

function useInvalidate() {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: ["payouts"] });
    qc.invalidateQueries({ queryKey: ["earnings"] });
  };
}

export function useQuotePayoutMutation() {
  return useMutation({ mutationFn: (req: QuotePayoutRequest) => service.quotePayout(req) });
}

export function useRequestPayoutMutation() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (req: RequestPayoutRequest) => service.requestPayout(req),
    onSuccess: invalidate,
  });
}

export function useCancelPayoutMutation() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payoutId: string) => service.cancelPayout(payoutId),
    onSuccess: invalidate,
  });
}

export function useResolveBankAccountMutation() {
  return useMutation({ mutationFn: (req: ResolveBankAccountRequest) => service.resolveBankAccount(req) });
}

export function useAddBankAccountMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: AddBankAccountRequest) => service.addBankAccount(req),
    onSuccess: () => qc.invalidateQueries({ queryKey: payoutKeys.bankAccounts() }),
  });
}

export function useRemoveBankAccountMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (accountId: string) => service.removeBankAccount(accountId),
    onSuccess: () => qc.invalidateQueries({ queryKey: payoutKeys.bankAccounts() }),
  });
}

export { service as payoutService };
