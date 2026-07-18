import { createStore } from "zustand/vanilla";
import type { AuthSession } from "@components/website/auth/models";

/**
 * Session-recovery state bridge between the plain-TS `FetchHttpClient` and React.
 *
 * The client can't render UI, and the globally-mounted `SessionRecoveryOverlay`
 * can't observe fetch internals — this vanilla Zustand store is the contract
 * between them. State (not events) so an overlay that mounts after a transition
 * still sees the current phase.
 *
 * Phases:
 * - `idle`         — no recovery in progress (routine refreshes stay invisible).
 * - `reconnecting` — a transient refresh failure occurred and retries are in
 *                    flight; `attempt`/`maxAttempts` drive "Attempt 2 of 3" copy.
 * - `expired`      — the session is unrecoverable (definitive rejection or retry
 *                    budget exhausted); the overlay redirects to `redirectTo`.
 */
export type SessionRecoveryPhase = "idle" | "reconnecting" | "expired";

export interface SessionRecoveryState {
  phase: SessionRecoveryPhase;
  /** 1-based attempt currently in flight; 0 outside recovery. */
  attempt: number;
  maxAttempts: number;
  /** Login target once expired; only meaningful in the `expired` phase. */
  redirectTo: string | null;
  /**
   * Session DTO from the last successful refresh. The React bridge pipes it
   * into `useAuthStore` (keeping accessTokenExpiresAt fresh for the proactive
   * keep-alive) and then consumes it — `src/lib` must not import components.
   */
  refreshedSession: AuthSession | null;
}

const INITIAL: SessionRecoveryState = {
  phase: "idle",
  attempt: 0,
  maxAttempts: 0,
  redirectTo: null,
  refreshedSession: null,
};

export const sessionRecoveryStore = createStore<SessionRecoveryState>(() => ({ ...INITIAL }));

/** A transient refresh failure happened; retry `attempt` of `maxAttempts` is starting. */
export function publishReconnecting(attempt: number, maxAttempts: number): void {
  sessionRecoveryStore.setState({ phase: "reconnecting", attempt, maxAttempts });
}

/** Refresh succeeded — close any recovery UI and hand the fresh session to the React bridge. */
export function publishRecovered(session: AuthSession | null): void {
  sessionRecoveryStore.setState({ ...INITIAL, refreshedSession: session });
}

/**
 * The session is unrecoverable. A `null` target means the failure happened on
 * the auth surface (see `loginRedirectUrl`) where 401s are legitimate — reset
 * to idle instead of blocking the login page.
 */
export function publishExpired(redirectTo: string | null): void {
  if (redirectTo === null) {
    sessionRecoveryStore.setState({ ...INITIAL });
    return;
  }
  sessionRecoveryStore.setState({ phase: "expired", attempt: 0, redirectTo });
}

/** React bridge: take the pending refreshed session (once) for `useAuthStore`. */
export function consumeRefreshedSession(): AuthSession | null {
  const session = sessionRecoveryStore.getState().refreshedSession;
  if (session) {
    sessionRecoveryStore.setState({ refreshedSession: null });
  }
  return session;
}

/** Back to a clean slate (used by tests and the overlay's sign-in handoff). */
export function resetSessionRecovery(): void {
  sessionRecoveryStore.setState({ ...INITIAL });
}
