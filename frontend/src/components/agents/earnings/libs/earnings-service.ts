import { httpClient } from "@/containers";

export interface EarningsSummary {
  totalLifetime: number;
  totalPending: number;
  totalAvailable: number;
  totalPaid: number;
}

export interface EarningRecord {
  id: string;
  taskId: string;
  verificationId: string;
  grossAmount: number;
  commissionPct: number;
  netAmount: number;
  status: string;
  computedAt: string;
}

export interface CommissionRule {
  id: string;
  role: string;
  tier: string;
  percentage: number;
  effectiveDate: string;
}

export class EarningsService {
  getSummary(): Promise<{ data: EarningsSummary }> {
    return httpClient.get("/agent/earnings");
  }

  listJobs(): Promise<{ data: EarningRecord[] }> {
    return httpClient.get("/agent/earnings/jobs");
  }
}

export class CommissionAdminService {
  listRules(): Promise<{ data: CommissionRule[] }> {
    return httpClient.get("/admin/commission-rules");
  }

  createRule(data: Omit<CommissionRule, "id">): Promise<{ data: CommissionRule }> {
    return httpClient.post("/admin/commission-rules", data);
  }

  updateRule(id: string, data: Partial<Omit<CommissionRule, "id">>): Promise<{ data: CommissionRule }> {
    return httpClient.put(`/admin/commission-rules/${id}`, data);
  }
}

export const earningsService = new EarningsService();
export const commissionAdminService = new CommissionAdminService();
