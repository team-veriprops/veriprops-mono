// Automation window hooks (__auth_snapshot__, __TEST_MODE__, __oauth_complete__, …)
// are gated by this allowlist. It is deliberately fail-closed / default-deny: any value
// NOT listed here — including "staging", "production", and an unset/empty value — returns
// false, so a prod/staging build (or a build with the var missing) can never activate the
// hooks. Only these three explicitly-non-production values enable automation.
const AUTOMATION_ENVS = [
  "dev_personal",
  "development",
  "test",
] as const;

// Environments that must never expose automation hooks, asserted explicitly as a second
// line of defense so a future edit to AUTOMATION_ENVS can't accidentally include them.
const NON_AUTOMATION_ENVS = ["staging", "production"] as const;

type AutomationEnv = (typeof AUTOMATION_ENVS)[number];

export function isAutomationEnvironment(): boolean {
  const env = process.env.NEXT_PUBLIC_ENVIRONMENT;

  if (!env || (NON_AUTOMATION_ENVS as readonly string[]).includes(env)) {
    return false;
  }

  return AUTOMATION_ENVS.includes(env as AutomationEnv);
}

/** The auth slice `__auth_snapshot__` exposes — kept minimal and PII-light on purpose. */
export interface AuthSnapshotSource {
  user?: { id?: string | null; personas?: string[] | null } | null;
}

/**
 * Publish the current session to `window.__auth_snapshot__` — automation's single source
 * of truth for "is this page signed in, and as whom".
 *
 * Called from the auth store's setters so **every** path that changes the session
 * (login, signup, session query, token refresh, logout) keeps the hook accurate. Writing
 * it from only one of those paths is what made a freshly-logged-in page look signed out.
 * No-ops outside automation environments (fail-closed via `isAutomationEnvironment`).
 */
export function publishAuthSnapshot(session: AuthSnapshotSource | null): void {
  if (typeof window === "undefined" || !isAutomationEnvironment()) return;

  window.__auth_snapshot__ = {
    isAuthenticated: !!session,
    userId: session?.user?.id ?? null,
    personas: (session?.user?.personas ?? []) as NonNullable<
      Window["__auth_snapshot__"]
    >["personas"],
  };
}