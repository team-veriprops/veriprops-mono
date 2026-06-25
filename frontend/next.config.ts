import { serverConfig } from "./src/lib/config/server";
import { publicConfig } from "./src/lib/config/public";
import type { NextConfig } from "next";


const nextConfig: NextConfig = {
  // The rewrite proxy resets upstream requests after proxyTimeout (default 30s),
  // which severs long synchronous calls like the cold-start seed (~76s of live
  // LLM evaluation) — the backend finishes but the browser sees a socket hang up.
  // Raise it well above the slowest endpoint.
  experimental: { proxyTimeout: 180_000 },
  allowedDevOrigins: ["127.0.0.1", "localhost", "172.22.48.1"],
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

