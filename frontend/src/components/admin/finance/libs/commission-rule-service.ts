import { HttpClient } from "@lib/FetchHttpClient";
import { SuccessResponse } from "@/types/models";
import { CommissionRule, SetCommissionRuleRequest } from "@/types/commission";
import { AgentRole } from "@/types/agent";

/**
 * Commission Rules admin API (PRD §20.1 / D97) — one fixed commission per agent role. Mirrors
 * app/domain/commission_rule/controller.py — RBAC CONFIGURE_PRICING.
 */
export class CommissionRuleService {
  constructor(private readonly http: HttpClient) {}

  listRules(): Promise<SuccessResponse<CommissionRule[]>> {
    return this.http.get(`/admin/commission-rules`);
  }

  setRule(role: AgentRole, req: SetCommissionRuleRequest): Promise<SuccessResponse<CommissionRule>> {
    return this.http.put(`/admin/commission-rules/${role}`, req);
  }
}
