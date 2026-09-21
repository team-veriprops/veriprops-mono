// serverConfig throws if imported on the client, so this module is server-only.
import { serverConfig } from "@lib/config/server";
import type { SuccessResponse } from "@app-types/models";

/**
 * How a server-side backend read is cached: `no-store` for data that changes as a case
 * progresses, or an ISR `revalidate` window for backend-owned content that rarely changes.
 */
export type BackendFetchCaching = { cache: "no-store" } | { next: { revalidate: number } };

/**
 * Read `data` from the backend's success envelope at `/api{path}` for a server-rendered page.
 * Returns null for a non-2xx response or an envelope without data, so a page can render its
 * not-found or empty state instead of failing.
 */
export async function fetchBackendData<T>(
  path: string,
  caching: BackendFetchCaching,
): Promise<T | null> {
  const res = await fetch(`${serverConfig.backendApi}/api${path}`, {
    headers: { Accept: "application/json" },
    ...caching,
  });
  if (!res.ok) return null;
  const body = (await res.json()) as SuccessResponse<T>;
  return body.data ?? null;
}
