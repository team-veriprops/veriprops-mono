"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { DEFAULT_PAGE_SIZE } from "@lib/config/app";
import { httpClient } from "@/containers";
import { PayoutDecisionRequest } from "@/types/payout";
import { SetCommissionRuleRequest } from "@/types/commission";
import { AgentRole } from "@/types/agent";
import { AdminPayoutService } from "./admin-payout-service";
import { CommissionRuleService } from "./commission-rule-service";
import { AdminPaymentService } from "./admin-payment-service";

const payoutService = new AdminPayoutService(httpClient);
const ruleService = new CommissionRuleService(httpClient);
const paymentService = new AdminPaymentService(httpClient);

export const financeKeys = {
  payouts: (page: number, status: string) => ["admin-payouts", page, status] as const,
  commissionRules: () => ["commission-rules"] as const,
  refundRetries: (page: number) => ["refund-retries", page] as const,
};

// ── Refunds a gateway refused ──────────────────────────────────────
export function useRefundRetriesQuery(page = 0, pageSize = DEFAULT_PAGE_SIZE) {
  return useQuery({
    queryKey: financeKeys.refundRetries(page),
    queryFn: async () => (await paymentService.listRefundRetries(page, pageSize)).data,
    // A 403 means this admin may not refund; the section hides rather than retrying.
    retry: false,
  });
}

export function useRetryRefundMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (paymentId: string) => paymentService.retryRefund(paymentId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["refund-retries"] }),
  });
}

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
    mutationFn: (v: { role: AgentRole; req: SetCommissionRuleRequest }) => ruleService.setRule(v.role, v.req),
    onSuccess: () => qc.invalidateQueries({ queryKey: financeKeys.commissionRules() }),
  });
}

export { payoutService as adminPayoutService, ruleService as commissionRuleService };
