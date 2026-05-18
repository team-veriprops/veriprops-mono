import { HttpClient } from "@lib/FetchHttpClient";
import { SuccessResponse } from "@/types/models";

export interface AbandonedVerificationSummary {
  id: string;
  vid: string;
  tier: string;
  status: string;
  propertyState: string | null;
  propertyLga: string | null;
  propertyAddress: string | null;
  totalAmountMinor: number | null;
  currency: string | null;
  dateUpdated: string | null;
  dateCreated: string;
}

export interface DashboardSummary {
  total: number;
  active: number;
  completed: number;
  unreadReportCount: number;
  abandoned: AbandonedVerificationSummary[];
}

export class DashboardService {
  constructor(private readonly client: HttpClient) {}

  fetchSummary(): Promise<SuccessResponse<DashboardSummary>> {
    return this.client.get("/portal/dashboard/summary");
  }
}
