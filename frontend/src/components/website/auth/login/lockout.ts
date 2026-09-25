import { isCredentialRejection } from "@lib/errors";
import { RATE_LIMIT_LOCKOUT_AT, RATE_LIMIT_LOCKOUT_MINUTES } from "../schemas";

/**
 * The sign-in form's client-side lockout: after `RATE_LIMIT_LOCKOUT_AT` rejected passwords the
 * form pauses for `RATE_LIMIT_LOCKOUT_MINUTES`. Persisted in localStorage so a reload doesn't
 * reset it.
 */

const LOCKOUT_KEY = "veriprops-login-lockout";
const ATTEMPTS_KEY = "veriprops-login-attempts";

export interface LockoutState {
  count: number;
  lockedUntil?: number; // epoch ms
}

export function readLockoutState(): LockoutState {
  if (typeof window === "undefined") return { count: 0 };
  try {
    const raw = localStorage.getItem(LOCKOUT_KEY);
    return raw ? (JSON.parse(raw) as LockoutState) : { count: 0 };
  } catch {
    return { count: 0 };
  }
}

export function writeLockoutState(state: LockoutState) {
  try {
    localStorage.setItem(LOCKOUT_KEY, JSON.stringify(state));
    localStorage.setItem(ATTEMPTS_KEY, String(state.count));
  } catch {
    /* noop */
  }
}

/**
 * The lockout after a failed sign-in.
 *
 * Only a rejected password counts. A server failure or a lost connection says nothing about the
 * password, and counting it would lock people out during an outage that is ours.
 *
 * Lives outside the component (rather than inline in the submit handler) so the `Date.now()` call
 * isn't flagged as an impure render call — React Compiler can't prove `onSubmit` only runs from an
 * event, since it's invoked indirectly via `form.handleSubmit(onSubmit)`.
 */
export function lockoutAfterFailure(current: LockoutState, error: unknown): LockoutState {
  if (!isCredentialRejection(error)) return current;
  const next: LockoutState = { count: current.count + 1 };
  if (next.count >= RATE_LIMIT_LOCKOUT_AT) {
    next.lockedUntil = Date.now() + RATE_LIMIT_LOCKOUT_MINUTES * 60_000;
  }
  return next;
}
