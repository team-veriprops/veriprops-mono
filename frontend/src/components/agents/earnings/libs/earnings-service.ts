import { HttpClient } from "@lib/FetchHttpClient";
import { Page, SuccessResponse } from "@/types/models";
import { EarningJob, EarningsSummary } from "@/types/earnings";

/**
 * Agent earnings API (PRD §15.1). Mirrors the backend controller at
 * app/domain/earnings/controller.py — the balance is derived server-side (D31); the
 * frontend renders it, never recomputes it.
 */
export class EarningsService {
  constructor(private readonly http: HttpClient) {}

  getSummary(): Promise<SuccessResponse<EarningsSummary>> {
    return this.http.get(`/agents/earnings`);
  }

  listJobs(page = 0, pageSize = 10): Promise<SuccessResponse<Page<EarningJob>>> {
    return this.http.get(`/agents/earnings/jobs?page=${page}&page_size=${pageSize}`);
  }
}
