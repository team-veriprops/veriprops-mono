import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import { AuthSession, AuthUser } from "@components/website/auth/models";
import { publishAuthSnapshot } from "@lib/automation";
/**
 * Lightweight client-side mirror of the auth session. The httpOnly access token
 * lives in a cookie (managed by `FetchHttpClient`); this store only holds the
 * user-facing slice needed for portal routing and personalisation.
 *
 * Every session mutation republishes the automation `__auth_snapshot__` hook, so the
 * hook is accurate no matter which path (login, signup, session query, refresh, logout)
 * changed the session.
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
      setSession: (session) => {
        publishAuthSnapshot(session);
        set({ session, pendingLogout: false });
      },
      setUser: (user) =>
        set((state) => {
          if (!state.session) return {};
          const session = { ...state.session, user };
          publishAuthSnapshot(session);
          return { session };
        }),
      setPendingLogout: (pending) => set({ pendingLogout: pending }),
      clear: () => {
        publishAuthSnapshot(null);
        set({ session: null });
      },
      markHydrated: () => set({ hydrated: true }),
    }),
    {
      name: "veriprops-auth",
      storage: createJSONStorage(() => localStorage),
      partialize: (state: AuthState) => ({ session: state.session, pendingLogout: state.pendingLogout }),
      onRehydrateStorage: () => (state: AuthState | undefined) => {
        // A returning user's session arrives via rehydration, not a setter — publish it
        // so the automation snapshot is accurate on the very first render too.
        publishAuthSnapshot(state?.session ?? null);
        state?.markHydrated();
      },
    },
  ),
);
