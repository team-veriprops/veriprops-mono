"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { httpClient } from "@/containers";
import { AddBankAccountRequest, RequestPayoutRequest } from "@/types/payout";
import { PayoutService } from "./payout-service";

const service = new PayoutService(httpClient);

export const payoutKeys = {
  list: (page: number) => ["payouts", page] as const,
  bankAccounts: () => ["payout-bank-accounts"] as const,
};

export function usePayoutsQuery(page = 0, pageSize = 10) {
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

function useInvalidate() {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: ["payouts"] });
    qc.invalidateQueries({ queryKey: ["earnings"] });
  };
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
