import { HttpClient } from "@lib/FetchHttpClient";
import { SuccessResponse } from "@/types/models";

export interface ReferralStats {
  code: string;
  referralLink: string;
  totalInvited: number;
  totalCredited: number;
  pendingCount: number;
  creditBalanceNgn: number;
}

export interface ClaimReferralRequest {
  code: string;
}

export class ReferralService {
  private readonly base = "/referrals";

  constructor(private readonly http: HttpClient) {}

  getMyStats(): Promise<SuccessResponse<ReferralStats>> {
    return this.http.get(`${this.base}/my-stats`);
  }

  claimReferral(payload: ClaimReferralRequest): Promise<SuccessResponse<void>> {
    return this.http.post(`${this.base}/claim`, payload);
  }
}
