// Server-only: reads through backend-fetch.server, which imports serverConfig.
import type { LegalDocument, LegalDocumentSummary } from "@app-types/models";

import { fetchBackendData } from "./backend-fetch.server";

// Reads the public legal documents for the /legal/[slug] pages and the sitemap.

const CONSENT_DOCUMENTS_PATH = "/users/auth/consents/documents";
const LEGAL_CACHING = { next: { revalidate: 3600 } };

export async function fetchLegalDocument(slug: string): Promise<LegalDocument | null> {
  return fetchBackendData<LegalDocument>(
    `${CONSENT_DOCUMENTS_PATH}/${encodeURIComponent(slug)}`,
    LEGAL_CACHING,
  );
}

export async function fetchLegalDocuments(): Promise<LegalDocumentSummary[]> {
  const data = await fetchBackendData<{ documents: LegalDocumentSummary[] }>(
    CONSENT_DOCUMENTS_PATH,
    LEGAL_CACHING,
  );
  return data?.documents ?? [];
}
