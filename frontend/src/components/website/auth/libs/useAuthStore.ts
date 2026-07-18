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
  /** Set when a logout call never reached the backend (offline) — flushed by
   * `usePendingLogoutRetry` and cleared by any successful `setSession` (see
   * that hook for why a re-confirmed session always wins over a stale intent). */
  pendingLogout: boolean;
  hydrated: boolean;
  setSession: (session: AuthSession | null) => void;
  setUser: (user: AuthUser) => void;
  setPendingLogout: (pending: boolean) => void;
  clear: () => void;
  markHydrated: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      session: null,
      pendingLogout: false,
      hydrated: false,
      setSession: (session) => set({ session, pendingLogout: false }),
      setUser: (user) =>
        set((state) => (state.session ? { session: { ...state.session, user } } : {})),
      setPendingLogout: (pending) => set({ pendingLogout: pending }),
      clear: () => set({ session: null }),
      markHydrated: () => set({ hydrated: true }),
    }),
    {
      name: "veriprops-auth",
      storage: createJSONStorage(() => localStorage),
      partialize: (state: AuthState) => ({ session: state.session, pendingLogout: state.pendingLogout }),
      onRehydrateStorage: () => (state: AuthState | undefined) => state?.markHydrated(),
    },
  ),
);
