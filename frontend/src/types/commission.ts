import { AgentRole } from "@/types/agent";
import { VerificationTier } from "@/types/verification";

/** Admin per-role×tier commission rate in basis points (§15.1 / D30). */
export interface CommissionRule {
  id: string;
  role: AgentRole;
  tier: VerificationTier;
  rateBps: number;
  dateCreated: string;
}

export interface SetCommissionRuleRequest {
  rateBps: number;
}
