// import { usePropertyStore } from "@components/website/property/usePropertyStore";
import { Language, TransactionCurrency, PropertyType } from "@/types/models";
import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface GlobalSettings {
  language: Language;
  currency: TransactionCurrency;
  propertyType: PropertyType;
  rowsPerPage: number; // Number of rows in a page of paginated dataset
  firstPage: number; // The first page number 0 | 1
  searchDebounceSeconds: number;
  searchQueryKey: string;
  currentTime: Date;
}

const defaultSettings: GlobalSettings = {
  language: Language.ENGLISH,
  currency: TransactionCurrency.NGN,
  propertyType: PropertyType.LAND,
  rowsPerPage: 5,
  firstPage: 0,
  searchDebounceSeconds: 300,
  searchQueryKey: "query",
  currentTime: new Date(),
} as const;

interface GlobalSettingsState {
  settings: GlobalSettings;
  setLanguage: (language: Language) => void;
  setCurrency: (currency: TransactionCurrency) => void;
  setPropertyType: (propertyType: PropertyType) => void;
  setSettings: (settings: GlobalSettings) => void;
  reset: () => void;
  setRowsPerPage: (rowsPerPage: number) => void;
  setFirstPage: (firstPage: number) => void;
  setSearchDebounceSeconds: (searchDebounceSeconds: number) => void;
  setSearchQueryKey: (searchQueryKey: string) => void;
  setCurrentTime: (currentTime: string) => void;
}

export const useGlobalSettings = create<GlobalSettingsState>()(
  persist(
    (set) => ({
      settings: defaultSettings,
      setLanguage: (language) =>
        set((state) => ({
          settings: { ...state.settings, language },
        })),
      setCurrency: (currency) =>
        set((state) => ({
          settings: { ...state.settings, currency },
        })),
      setPropertyType: (propertyType) => {
        set((state) => ({
          settings: { ...state.settings, propertyType },
        }));

        // // Sync to PropertyStore
        // usePropertyStore.getState().updateFilter("type", propertyType);
      },
      setSettings: (settings) => set({ settings }),
      reset: () =>
        set({
          settings: defaultSettings,
        }),
      setRowsPerPage: (rowsPerPage) =>
        set((state) => ({
          settings: { ...state.settings, rowsPerPage },
        })),
      setFirstPage: (firstPage) =>
        set((state) => ({
          settings: { ...state.settings, firstPage },
        })),
      setSearchDebounceSeconds: (searchDebounceSeconds) =>
        set((state) => ({
          settings: { ...state.settings, searchDebounceSeconds },
        })),
      setSearchQueryKey: (searchQueryKey) =>
        set((state) => ({
          settings: { ...state.settings, searchQueryKey },
        })),
      setCurrentTime: (currentTime) =>
        set((state) => ({
          settings: { ...state.settings, currentTime: new Date(currentTime) },
        })),
    }),
    {
      name: "veriprops-global_settings", // key in localStorage
    }
  )
);
