"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { DEFAULT_PAGE_SIZE } from "@lib/config/app";
import { httpClient } from "@/containers";
import { PayoutDecisionRequest } from "@/types/payout";
import { SetCommissionRuleRequest } from "@/types/commission";
import { AgentRole } from "@/types/agent";
import { VerificationTier } from "@/types/verification";
import { AdminPayoutService } from "./admin-payout-service";
import { CommissionRuleService } from "./commission-rule-service";

const payoutService = new AdminPayoutService(httpClient);
const ruleService = new CommissionRuleService(httpClient);

export const financeKeys = {
  payouts: (page: number, status: string) => ["admin-payouts", page, status] as const,
  commissionRules: () => ["commission-rules"] as const,
};

// ── Payouts ────────────────────────────────────────────────────────
export function useAdminPayoutsQuery(page = 0, pageSize = DEFAULT_PAGE_SIZE, status = "") {
  return useQuery({
    queryKey: financeKeys.payouts(page, status),
    queryFn: async () => (await payoutService.listPayouts(page, pageSize, status || undefined)).data ?? null,
  });
}

type DecisionAction = "approve" | "hold" | "adjust" | "reject";

export function usePayoutDecisionMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { action: DecisionAction; payoutId: string; req?: PayoutDecisionRequest }) =>
      payoutService[v.action](v.payoutId, v.req ?? {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-payouts"] }),
  });
}

// ── Commission rules ───────────────────────────────────────────────
export function useCommissionRulesQuery() {
  return useQuery({
    queryKey: financeKeys.commissionRules(),
    queryFn: async () => (await ruleService.listRules()).data ?? [],
  });
}

export function useSetCommissionRuleMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { tier: VerificationTier; role: AgentRole; req: SetCommissionRuleRequest }) =>
      ruleService.setRule(v.tier, v.role, v.req),
    onSuccess: () => qc.invalidateQueries({ queryKey: financeKeys.commissionRules() }),
  });
}

export { payoutService as adminPayoutService, ruleService as commissionRuleService };
