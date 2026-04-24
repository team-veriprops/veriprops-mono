import { create } from "zustand";
import { QueryBankDto, SearchBankDto} from "../models";
import { BankService } from "./bank-service";
import { createJSONStorage, persist } from "zustand/middleware";
import { httpClient } from "@/containers";

const defaultFilters: Partial<SearchBankDto> = {
  page: 0,
  pageSize: 6,
};

const cloneDefaultFilters = (): Partial<SearchBankDto> => ({
  ...defaultFilters,
});

interface BankStore {
  service: BankService; // runtime only (not persisted)
  filters: Partial<SearchBankDto>; // persisted + synced with query params
  currentBank: QueryBankDto | null; // persisted only
  viewBankDetail: boolean;
  updateFilters: (updates: Partial<SearchBankDto>) => void; // <—
  setCurrentBank: (currentBank: QueryBankDto | null) => void;
  setViewBankDetail: (viewBankDetail: boolean) => void;
}

// runtime service instance (not persisted)
const service = new BankService(httpClient);

export const useBankStore = create<BankStore>()(
  persist(
    (set) => ({
      service,
      filters: cloneDefaultFilters(),
      currentBank: null,
      viewBankDetail: false,
      // update multiple filter keys at once
      updateFilters: (updates) =>
        set((state) => ({
          filters: { ...state.filters, ...updates },
        })),

      // update the currently selected Bank
      setCurrentBank: (currentBank) => set({ currentBank }),
      setViewBankDetail: (viewBankDetail) => set({ viewBankDetail }),
    }),
    {
      name: "veriprops-Bank", // localStorage key
      storage: createJSONStorage(() => localStorage), // hydration-safe
      // Persist only filters + currentBank, skip service
      partialize: (state: { filters: SearchBankDto; currentBank: QueryBankDto; viewBankDetail: boolean }) => ({
        filters: state.filters,
        currentBank: state.currentBank,
        viewBankDetail: state.viewBankDetail,
      }),
    }
  )
);
