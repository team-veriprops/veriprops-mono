const AUTOMATION_ENVS = [
  "local",
  "development",
  "test",
] as const;

type AutomationEnv = (typeof AUTOMATION_ENVS)[number];

export function isAutomationEnvironment(): boolean {
  const env = process.env.NEXT_PUBLIC_ENVIRONMENT;

  return AUTOMATION_ENVS.includes(env as AutomationEnv);
}