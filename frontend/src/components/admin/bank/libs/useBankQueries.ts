import { useQueryClient, useQuery, useMutation } from "@tanstack/react-query";
import {
  CreateBankDto,
  QueryBankDto,
  SearchBankDto,
  UpdateBankDto,
} from "../models";
import { Page, SuccessResponse } from "@/types/models";
import { useShallow } from "zustand/react/shallow";
import { stringifyFilters } from "@lib/utils";
import { useBankStore } from "./useBankStore";

/**
 * React Query hooks wrapping BankService
 */
export const useBankQueries = () => {
  const service = useBankStore((state) => state.service);
  const filters = useBankStore(useShallow((state) => state.filters));
  const queryClient = useQueryClient();
  const normalizedFilters = stringifyFilters(filters);

  const useCreateBank = () =>
    useMutation({
      mutationFn: (payload: CreateBankDto) =>
        service.createBank(payload),
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: ["create-Bank"],
        });
      },
    });

  const useGetBank = (bankId: string) => 
      useQuery<SuccessResponse<QueryBankDto>>({
        queryKey: ["get-invited_user", bankId] as const,
        queryFn: async (): Promise<SuccessResponse<QueryBankDto>> => service.getBank(bankId),
        placeholderData: (prev) => prev,
        enabled: !bankId
  });

  const useSearchBankPage = () =>
    useQuery<Page<QueryBankDto>>({
      queryKey: ["Banks", normalizedFilters],
      queryFn: async (): Promise<Page<QueryBankDto>> =>
        service.searchBankPage(filters as SearchBankDto),
      placeholderData: (prev) => prev,
      // enabled: !!company_id, // only fetch if company_id exists
  });

  const useUpdateBank = () =>
    useMutation({
      mutationFn: ({ bankId, payload }: { bankId: string; payload: UpdateBankDto }) =>
        service.updateBank(bankId, payload),
  });

  const useDeactivateBank = () =>
    useMutation({
      mutationFn: (bankId: string) =>
        service.deactivateBank(bankId),
  });

  const useActivateBank = () =>
    useMutation({
      mutationFn: (bankId: string) =>
        service.activateBank(bankId),
  });

  const useDeleteBank = () =>
    useMutation({
      mutationFn: (bankId: string) =>
        service.deleteBank(bankId),
  });

  return {
    useCreateBank,
    useGetBank,
    useSearchBankPage,
    useUpdateBank,
    useDeactivateBank,
    useActivateBank,
    useDeleteBank
  };
};
