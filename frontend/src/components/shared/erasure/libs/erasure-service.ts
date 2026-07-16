import { HttpClient } from "@lib/FetchHttpClient";
import { DEFAULT_PAGE_SIZE } from "@lib/config/app";
import { Page, SuccessResponse } from "@/types/models";
import { DataErasureRequest } from "@/types/erasure";

/**
 * NDPA data-erasure API (PRD §18.1, §19.1). Mirrors the backend controllers at
 * app/domain/compliance/erasure/controller.py. Self-service routes are the data
 * subject's own (Account → Data & privacy); admin routes require MANAGE_COMPLIANCE.
 * Shared by the account + admin surfaces (single source of truth — no duplication).
 */
export class ErasureService {
  constructor(private readonly http: HttpClient) {}

  // ── Self-service (data subject) ──
  requestMine(reason?: string): Promise<SuccessResponse<DataErasureRequest>> {
    return this.http.post(`/users/me/erasure-requests`, { reason });
  }

  listMine(): Promise<SuccessResponse<DataErasureRequest[]>> {
    return this.http.get(`/users/me/erasure-requests`);
  }

  // ── Admin review (MANAGE_COMPLIANCE) ──
  list(status: string | undefined, page = 0, pageSize = DEFAULT_PAGE_SIZE): Promise<SuccessResponse<Page<DataErasureRequest>>> {
    const q = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (status) q.set("status", status);
    return this.http.get(`/admin/erasure-requests?${q.toString()}`);
  }

  get(id: string): Promise<SuccessResponse<DataErasureRequest>> {
    return this.http.get(`/admin/erasure-requests/${id}`);
  }

  approve(id: string): Promise<SuccessResponse<DataErasureRequest>> {
    return this.http.post(`/admin/erasure-requests/${id}/approve`, {});
  }

  reject(id: string, note?: string): Promise<SuccessResponse<DataErasureRequest>> {
    return this.http.post(`/admin/erasure-requests/${id}/reject`, { note });
  }

  execute(id: string): Promise<SuccessResponse<DataErasureRequest>> {
    return this.http.post(`/admin/erasure-requests/${id}/execute`, {});
  }
}
