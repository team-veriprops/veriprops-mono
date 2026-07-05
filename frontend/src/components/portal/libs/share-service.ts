import { HttpClient } from "@lib/FetchHttpClient";
import { SuccessResponse } from "@/types/models";
import {
  CreateShareRequest,
  PublicSummary,
  Share,
  SharedReport,
} from "@/types/share";

/**
 * Report sharing API (PRD §13). Mirrors the backend controllers at
 * `app/domain/verification/share` — the customer-owned share management endpoints and
 * the unauthenticated public lookup / shared-token endpoints. Backend owns the summary
 * allow-list; the frontend renders what it receives and never recomputes it.
 */
export class ShareService {
  constructor(private readonly http: HttpClient) {}

  // ── Customer share management (authenticated) ──────────────────
  listShares(verificationId: string): Promise<SuccessResponse<Share[]>> {
    return this.http.get(`/verifications/${verificationId}/shares`);
  }

  createShare(
    verificationId: string,
    req: CreateShareRequest,
  ): Promise<SuccessResponse<Share>> {
    return this.http.post(`/verifications/${verificationId}/shares`, req);
  }

  revokeShare(
    verificationId: string,
    shareId: string,
  ): Promise<SuccessResponse<Share>> {
    return this.http.post(`/verifications/${verificationId}/shares/${shareId}/revoke`, {});
  }

  setPublicVisibility(
    verificationId: string,
    enabled: boolean,
  ): Promise<SuccessResponse<{ enabled: boolean }>> {
    return this.http.put(`/verifications/${verificationId}/public-visibility`, { enabled });
  }

  // ── Public (unauthenticated) ───────────────────────────────────
  publicLookup(vid: string): Promise<SuccessResponse<PublicSummary>> {
    return this.http.get(`/public/verify/${vid}`);
  }

  resolveShared(token: string): Promise<SuccessResponse<SharedReport>> {
    return this.http.get(`/public/shared/${token}`);
  }

  acknowledgeShared(token: string): Promise<SuccessResponse<SharedReport>> {
    return this.http.post(`/public/shared/${token}/acknowledge`, {});
  }
}
