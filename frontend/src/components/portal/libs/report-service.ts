import { HttpClient } from "@lib/FetchHttpClient";
import { SuccessResponse } from "@/types/models";
import { CustomerReport } from "@/types/report";

/**
 * Customer report API (PRD §10). Mirrors the backend controller at
 * `app/domain/verification/report`. Backend owns the verdict, trust band and section
 * content — the frontend renders them and never recomputes.
 */
export class ReportService {
  constructor(private readonly http: HttpClient) {}

  getReport(id: string): Promise<SuccessResponse<CustomerReport>> {
    return this.http.get(`/verifications/${id}/report`);
  }

  /** Records the one-time access-gate acknowledgement against the report version. */
  acknowledge(id: string): Promise<SuccessResponse<CustomerReport>> {
    return this.http.post(`/verifications/${id}/report/acknowledge`, {});
  }

  /** Proxied server-side PDF download URL (branded, legal footer on every page). */
  pdfUrl(id: string): string {
    return `/api/verifications/${id}/report/pdf`;
  }
}
