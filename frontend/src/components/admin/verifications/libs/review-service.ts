import { HttpClient } from "@lib/FetchHttpClient";
import { SuccessResponse } from "@/types/models";
import { AgentRole } from "@/types/agent";
import { VerificationTier } from "@/types/verification";
import { ReviewState, TierWeights } from "@/types/adminReview";

/**
 * Admin review & report-release API. Mirrors the backend controllers at
 * `app/domain/verification/review` (`/admin/review/...`) and `scoring`
 * (`/admin/trust-score-weights/...`). Backend owns the release gate + composite score.
 */
export class ReviewService {
  private readonly base = "/admin/review";

  constructor(private readonly http: HttpClient) {}

  getReview(verificationId: string): Promise<SuccessResponse<ReviewState>> {
    return this.http.get(`${this.base}/${verificationId}`);
  }

  approveTask(verificationId: string, role: AgentRole, quality: number): Promise<SuccessResponse<ReviewState>> {
    return this.http.post(`${this.base}/${verificationId}/tasks/${role}/approve`, { quality });
  }

  rejectTask(verificationId: string, role: AgentRole, reason: string): Promise<SuccessResponse<ReviewState>> {
    return this.http.post(`${this.base}/${verificationId}/tasks/${role}/reject`, { reason });
  }

  reopenTask(verificationId: string, role: AgentRole): Promise<SuccessResponse<ReviewState>> {
    return this.http.post(`${this.base}/${verificationId}/tasks/${role}/reopen`, {});
  }

  release(verificationId: string, reason?: string): Promise<SuccessResponse<ReviewState>> {
    return this.http.post(`${this.base}/${verificationId}/release`, { reason });
  }

  fail(verificationId: string, reason: string): Promise<SuccessResponse<ReviewState>> {
    return this.http.post(`${this.base}/${verificationId}/fail`, { reason });
  }
}

/** Trust Score Weights admin CRUD (§8.3 / D14). */
export class TrustWeightService {
  private readonly base = "/admin/trust-score-weights";

  constructor(private readonly http: HttpClient) {}

  list(): Promise<SuccessResponse<TierWeights[]>> {
    return this.http.get(this.base);
  }

  setTierWeights(
    tier: VerificationTier,
    weights: Record<AgentRole, number>,
  ): Promise<SuccessResponse<TierWeights>> {
    return this.http.put(`${this.base}/${tier}`, { weights });
  }
}
