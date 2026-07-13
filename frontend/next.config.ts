import { serverConfig } from "./src/lib/config/server";
import { publicConfig } from "./src/lib/config/public";
import type { NextConfig } from "next";


const nextConfig: NextConfig = {
  // Emit a self-contained server (traced deps only) for a lean production image —
  // the Docker runner ships `.next/standalone` instead of the full node_modules.
  output: "standalone",
  // The rewrite proxy resets upstream requests after proxyTimeout (default 30s),
  // which severs long synchronous calls like the cold-start seed (~76s of live
  // LLM evaluation) — the backend finishes but the browser sees a socket hang up.
  // Raise it well above the slowest endpoint; override per-env via PROXY_TIMEOUT_MS.
  experimental: { proxyTimeout: Number(process.env.PROXY_TIMEOUT_MS ?? 180_000) },
  // Machine-specific dev hosts (e.g. a WSL/LAN IP) belong in a developer's local env,
  // never committed here. Set ADDITIONAL_DEV_ORIGINS as a comma-separated list.
  allowedDevOrigins: [
    "127.0.0.1",
    "localhost",
    ...(process.env.ADDITIONAL_DEV_ORIGINS?.split(",").map((o) => o.trim()).filter(Boolean) ?? []),
  ],
  async rewrites() {
    return [
      {
        source: `${publicConfig.apiUrl}/:path*`,  // All calls to /api/* on Next.js
        destination: `${serverConfig.backendApi}/api/:path*`,
        // Replace with your FastAPI backend (dev/prod)
      },
    ];
  },
};

export default nextConfig;

