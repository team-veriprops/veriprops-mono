import { create } from "zustand";

interface UIState {
  isShareModalOpen: boolean;
  setShareModalOpen: (open: boolean) => void;
}

export const useUIStore = create<UIState>((set) => ({
  isShareModalOpen: false,
  setShareModalOpen: (open) => set({ isShareModalOpen: open }),
}));