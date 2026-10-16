export const publicConfig = {
  apiUrl: process.env.NEXT_PUBLIC_API_PREFIX ?? "/api",
  appName: process.env.NEXT_PUBLIC_APP_NAME ?? "Veriprops",
  microsoftClarityProjectId: process.env.NEXT_PUBLIC_MICROSOFT_CLARITY_PROJECT_ID,
  environment: process.env.NEXT_PUBLIC_ENVIRONMENT,
};
