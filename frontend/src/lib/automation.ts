// Automation window hooks (__auth_snapshot__, __TEST_MODE__, __oauth_complete__, …)
// are gated by this allowlist. It is deliberately fail-closed / default-deny: any value
// NOT listed here — including "staging", "production", and an unset/empty value — returns
// false, so a prod/staging build (or a build with the var missing) can never activate the
// hooks. Only these three explicitly-non-production values enable automation.
const AUTOMATION_ENVS = [
  "local",
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