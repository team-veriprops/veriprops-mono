if (typeof window !== "undefined") {
  throw new Error("❌ serverConfig imported on the client");
}

export const serverConfig = {
  backendApi: process.env.API_BASE_URL!,
  secretKey: process.env.BACKEND_SECRET_KEY!,
  // Rewrite-proxy socket timeout (next.config.ts experimental.proxyTimeout) —
  // raised above Next's 30s default so a slow cold-start call isn't severed.
  proxyTimeoutMs: Number(process.env.PROXY_TIMEOUT_MS ?? 180_000),
};
