// serverConfig throws if imported on the client, so this module is server-only.
import { serverConfig } from "@lib/config/server";
import type { SuccessResponse } from "@app-types/models";
import type { PublicSummary } from "@/types/share";

// Unauthenticated VID lookup for the public /verify/[vid] page + its SEO metadata (§13.1).

const PUBLIC_BASE = `${serverConfig.backendApi}/api/public`;

export async function fetchPublicSummary(vid: string): Promise<PublicSummary | null> {
  const res = await fetch(`${PUBLIC_BASE}/verify/${encodeURIComponent(vid)}`, {
    headers: { Accept: "application/json" },
    // The lookup result changes as a verification completes / is shared; keep it fresh.
    cache: "no-store",
  });
  if (!res.ok) return null;
  const body = (await res.json()) as SuccessResponse<PublicSummary>;
  return body.data ?? null;
}
