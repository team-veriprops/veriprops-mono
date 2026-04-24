export const publicConfig = {
  apiUrl: "/api",
  appName: process.env.NEXT_PUBLIC_APP_NAME ?? "Veriprops",
  timeout: Number(process.env.NEXT_PUBLIC_API_TIMEOUT ?? 10000),
  microsoftClarityProjectId: process.env.NEXT_PUBLIC_MICROSOFT_CLARITY_PROJECT_ID,
  googleMapsApiKey: process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY
};
