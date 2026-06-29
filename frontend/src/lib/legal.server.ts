// serverConfig throws if imported on the client, so this module is server-only.
import { serverConfig } from "@lib/config/server";
import type {
  LegalDocument,
  LegalDocumentSummary,
  SuccessResponse,
} from "@app-types/models";

/**
 * Server-side reads of the public legal documents. These endpoints are
 * unauthenticated and crawlable; the backend owns the document content,
 * version, and sign-off status (single source of truth). Used by the
 * `/legal/[slug]` pages and the sitemap.
 */

const CONSENTS_BASE = `${serverConfig.backendApi}/api/users/auth/consents`;

async function getJson<T>(url: string): Promise<T | null> {
  const res = await fetch(url, {
    headers: { Accept: "application/json" },
    // Legal content changes rarely; revalidate hourly so edits propagate.
    next: { revalidate: 3600 },
  });
  if (!res.ok) return null;
  const body = (await res.json()) as SuccessResponse<T>;
  return body.data ?? null;
}

export async function fetchLegalDocument(slug: string): Promise<LegalDocument | null> {
  return getJson<LegalDocument>(`${CONSENTS_BASE}/documents/${encodeURIComponent(slug)}`);
}

export async function fetchLegalDocuments(): Promise<LegalDocumentSummary[]> {
  const data = await getJson<{ documents: LegalDocumentSummary[] }>(`${CONSENTS_BASE}/documents`);
  return data?.documents ?? [];
}
