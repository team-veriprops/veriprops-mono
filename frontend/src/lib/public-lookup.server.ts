// Server-only: reads through backend-fetch.server, which imports serverConfig.
import type { PublicSummary } from "@/types/share";

import { fetchBackendData } from "./backend-fetch.server";

// Unauthenticated VID lookup for the public /verify/[vid] page + its SEO metadata (§13.1).

export async function fetchPublicSummary(vid: string): Promise<PublicSummary | null> {
  // The lookup result changes as a verification completes / is shared; keep it fresh.
  return fetchBackendData<PublicSummary>(`/public/verify/${encodeURIComponent(vid)}`, {
    cache: "no-store",
  });
}
