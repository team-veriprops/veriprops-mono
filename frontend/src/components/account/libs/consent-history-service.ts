import { HttpClient } from "@lib/FetchHttpClient";
import { DEFAULT_HISTORY_PAGE_SIZE } from "@lib/config/app";
import { SuccessResponse } from "@/types/models";
import { UserConsentHistoryPage } from "@/types/consentHistory";

/**
 * Versioned consent history API (PRD §19.1 / R19.4). Mirrors the S57 routes in
 * app/domain/user/auth/consent/controller.py. The CSV download is a plain proxied link.
 */
export class ConsentHistoryService {
  constructor(private readonly http: HttpClient) {}

  history(page = 0, pageSize = DEFAULT_HISTORY_PAGE_SIZE): Promise<SuccessResponse<UserConsentHistoryPage>> {
    return this.http.get(`/users/auth/consents/history?page=${page}&page_size=${pageSize}`);
  }

  /** Proxied CSV download link for the user's full consent history. */
  downloadUrl(): string {
    return `/api/users/auth/consents/history/download`;
  }
}
