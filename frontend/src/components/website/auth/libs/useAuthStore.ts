import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import { AuthSession, AuthUser } from "@components/website/auth/models";
/**
 * Lightweight client-side mirror of the auth session. The httpOnly access token
 * lives in a cookie (managed by `FetchHttpClient`); this store only holds the
 * user-facing slice needed for portal routing and personalisation.
 */

interface AuthState {
  session: AuthSession | null;
  hydrated: boolean;
  setSession: (session: AuthSession | null) => void;
  setUser: (user: AuthUser) => void;
  clear: () => void;
  markHydrated: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      session: null,
      hydrated: false,
      setSession: (session) => set({ session }),
      setUser: (user) =>
        set((state) => (state.session ? { session: { ...state.session, user } } : {})),
      clear: () => set({ session: null }),
      markHydrated: () => set({ hydrated: true }),
    }),
    {
      name: "veriprops-auth",
      storage: createJSONStorage(() => localStorage),
      partialize: (state: AuthState) => ({ session: state.session }),
      onRehydrateStorage: () => (state: AuthState | undefined) => state?.markHydrated(),
    },
  ),
);
