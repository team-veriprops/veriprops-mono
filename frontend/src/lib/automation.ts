const AUTOMATION_ENVS = new Set([
  "local",
  "development",
  "test",
] as const);

export function isAutomationEnvironment(): boolean {
  const env = process.env.NEXT_PUBLIC_ENVIRONMENT;
  return AUTOMATION_ENVS.has(env ?? "");
}
