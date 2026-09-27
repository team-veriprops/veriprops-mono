import { AgentRole } from "@/types/agent";

/**
 * The fixed commission one approved task of a role pays, in NGN kobo (§20.1 / D97) — the same
 * on every tier. Mirrors CommissionRuleDto in app/domain/commission_rule/models.py.
 */
export interface CommissionRule {
  id: string;
  role: AgentRole;
  amountNgnKobo: number;
  dateCreated: string;
}

export interface SetCommissionRuleRequest {
  amountNgnKobo: number;
}
