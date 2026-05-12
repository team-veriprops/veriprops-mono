import { httpClient } from "@/containers";

export interface TierUpgradePreview {
  fromTier: string;
  toTier: string;
  deltaPrice: number;
}

export class UpgradeService {
  preview(verificationId: string): Promise<{ data: TierUpgradePreview }> {
    return httpClient.get(`/api/portal/verifications/${verificationId}/upgrade/preview`);
  }

  submit(verificationId: string, toTier: string): Promise<{ data: { id: string; status: string } }> {
    return httpClient.post(`/api/portal/verifications/${verificationId}/upgrade`, { toTier });
  }
}

export const upgradeService = new UpgradeService();
