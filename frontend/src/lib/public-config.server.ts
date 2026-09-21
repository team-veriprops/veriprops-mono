import type { PublicConfig } from "@app-types/models";

import { fetchBackendData } from "./backend-fetch.server";

/** How stale prerendered public config may get — bounds how long an admin's price edit
 * takes to reach public pages. */
export const PUBLIC_CONFIG_REVALIDATE_SECONDS = 300;

/**
 * The backend's public runtime config (live tier prices, feature flags) for server-rendered
 * pages, so the HTML carries the same backend-owned figures the client hydrates with.
 *
 * Null when the backend is unreachable: `next build` prerenders public pages without one, and
 * the page must still render — without the backend-owned figures — rather than fail the build.
 */
export async function fetchPublicConfig(): Promise<PublicConfig | null> {
  try {
    return await fetchBackendData<PublicConfig>("/config/public", {
      next: { revalidate: PUBLIC_CONFIG_REVALIDATE_SECONDS },
    });
  } catch {
    return null;
  }
}
