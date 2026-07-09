import { HttpClient } from "@lib/FetchHttpClient";
import { Page, SuccessResponse } from "@/types/models";
import {
  Broadcast,
  BroadcastAudience,
  BroadcastPreview,
  ComposeBroadcastRequest,
} from "@/types/broadcast";

/**
 * Broadcast API (PRD §18.1, D37). Mirrors the backend controller at
 * app/domain/broadcast/controller.py — audience resolution + fan-out are backend-owned.
 */
export class BroadcastService {
  constructor(private readonly http: HttpClient) {}

  list(page = 0, pageSize = 10, status?: string): Promise<SuccessResponse<Page<Broadcast>>> {
    const q = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (status) q.set("status", status);
    return this.http.get(`/admin/broadcasts?${q.toString()}`);
  }

  preview(audience: BroadcastAudience): Promise<SuccessResponse<BroadcastPreview>> {
    return this.http.get(`/admin/broadcasts/preview?audience=${audience}`);
  }

  get(id: string): Promise<SuccessResponse<Broadcast>> {
    return this.http.get(`/admin/broadcasts/${id}`);
  }

  compose(payload: ComposeBroadcastRequest): Promise<SuccessResponse<Broadcast>> {
    return this.http.post(`/admin/broadcasts`, payload);
  }

  send(id: string): Promise<SuccessResponse<Broadcast>> {
    return this.http.post(`/admin/broadcasts/${id}/send`);
  }

  cancel(id: string): Promise<SuccessResponse<Broadcast>> {
    return this.http.post(`/admin/broadcasts/${id}/cancel`);
  }
}
