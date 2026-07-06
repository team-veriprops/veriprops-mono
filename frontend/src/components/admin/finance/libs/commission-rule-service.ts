import { HttpClient } from "@lib/FetchHttpClient";
import { SuccessResponse } from "@/types/models";
import { CommissionRule, SetCommissionRuleRequest } from "@/types/commission";
import { AgentRole } from "@/types/agent";
import { VerificationTier } from "@/types/verification";

/**
 * Commission Rules admin API (PRD §15.1 / D30). Mirrors app/domain/commission_rule/controller.py
 * — RBAC CONFIGURE_PRICING.
 */
export class CommissionRuleService {
  constructor(private readonly http: HttpClient) {}

  listRules(): Promise<SuccessResponse<CommissionRule[]>> {
    return this.http.get(`/admin/commission-rules`);
  }

  setRule(
    tier: VerificationTier,
    role: AgentRole,
    req: SetCommissionRuleRequest,
  ): Promise<SuccessResponse<CommissionRule>> {
    return this.http.put(`/admin/commission-rules/${tier}/${role}`, req);
  }
}
