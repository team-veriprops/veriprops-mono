"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { DEFAULT_PAGE_SIZE } from "@lib/config/app";
import { httpClient } from "@/containers";
import { PayoutAction, PayoutDecisionRequest } from "@/types/payout";
import { SetCommissionRuleRequest } from "@/types/commission";
import { AgentRole } from "@/types/agent";
import { AdminPayoutService } from "./admin-payout-service";
import { CommissionRuleService } from "./commission-rule-service";
import { AdminPaymentService, PaymentListFilters } from "./admin-payment-service";
import { RefundRequestService } from "./refund-request-service";
import { RefundRequestStatus } from "@/types/closure";

const payoutService = new AdminPayoutService(httpClient);
const ruleService = new CommissionRuleService(httpClient);
const paymentService = new AdminPaymentService(httpClient);
const refundRequestService = new RefundRequestService(httpClient);

export const financeKeys = {
  payouts: (page: number, status: string) => ["admin-payouts", page, status] as const,
  disbursementQueue: () => ["admin-payouts", "disbursement-queue"] as const,
  commissionRules: () => ["commission-rules"] as const,
  refundRetries: (page: number) => ["refund-retries", page] as const,
  payments: (page: number, pageSize: number, filters: PaymentListFilters) => ["admin-payments", page, pageSize, filters] as const,
  refundRequests: (page: number, pageSize: number, status: string, orderBy: string) =>
    ["refund-requests", page, pageSize, status, orderBy] as const,
};

// ── Refund approvals: every customer refund waits for Finance ────────
export function useRefundRequestsQuery(
  page: number, status?: RefundRequestStatus, pageSize = DEFAULT_PAGE_SIZE, orderBy?: string,
) {
  return useQuery({
    queryKey: financeKeys.refundRequests(page, pageSize, status ?? "", orderBy ?? ""),
    queryFn: async () => (await refundRequestService.list(page, pageSize, status, orderBy)).data,
    placeholderData: (prev) => prev,
  });
}

function useRefundDecision<TArgs>(fn: (args: TArgs) => ReturnType<RefundRequestService["approve"]>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      // A decision moves the queue, the payments it refunded, and the case it closed or resumed.
      qc.invalidateQueries({ queryKey: ["refund-requests"] });
      qc.invalidateQueries({ queryKey: ["admin-payments"] });
      qc.invalidateQueries({ queryKey: ["refund-retries"] });
      qc.invalidateQueries({ queryKey: ["admin", "verifications"] });
    },
  });
}

export function useApproveRefundMutation() {
  return useRefundDecision(({ id, note }: { id: string; note?: string }) => refundRequestService.approve(id, note));
}

export function useRejectRefundMutation() {
  return useRefundDecision(({ id, note }: { id: string; note: string }) => refundRequestService.reject(id, note));
}

// ── Every payment (finance's payments list) ──────────────────────────
export function useAdminPaymentsQuery(page: number, filters: PaymentListFilters, pageSize = DEFAULT_PAGE_SIZE) {
  return useQuery({
    queryKey: financeKeys.payments(page, pageSize, filters),
    queryFn: async () => (await paymentService.list(page, pageSize, filters)).data,
    placeholderData: (prev) => prev,
  });
}

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
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["refund-retries"] });
      qc.invalidateQueries({ queryKey: ["admin-payments"] });
    },
  });
}

// ── Payouts ────────────────────────────────────────────────────────
export function useAdminPayoutsQuery(page = 0, pageSize = DEFAULT_PAGE_SIZE, status = "") {
  return useQuery({
    queryKey: financeKeys.payouts(page, status),
    queryFn: async () => (await payoutService.listPayouts(page, pageSize, status || undefined)).data ?? null,
  });
}

/** The finance actions a decision panel can take (the agent's CANCEL is not one). */
export type FinancePayoutAction = Exclude<PayoutAction, PayoutAction.CANCEL>;

const DECIDE: Record<FinancePayoutAction, (id: string, req: PayoutDecisionRequest) => Promise<unknown>> = {
  [PayoutAction.APPROVE]: (id, req) => payoutService.approve(id, req),
  [PayoutAction.HOLD]: (id, req) => payoutService.hold(id, req),
  [PayoutAction.ADJUST]: (id, req) => payoutService.adjust(id, req),
  [PayoutAction.REJECT]: (id, req) => payoutService.reject(id, req),
  [PayoutAction.RETRY]: (id) => payoutService.retry(id),
};

export function usePayoutDecisionMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { action: FinancePayoutAction; payoutId: string; req?: PayoutDecisionRequest }) =>
      DECIDE[v.action](v.payoutId, v.req ?? {}),
    // The queue count moves with approvals and retries, so it refreshes with the list. On an
    // error too: a refused retry may have found the transfer paid and settled it meanwhile.
    onSettled: () => qc.invalidateQueries({ queryKey: ["admin-payouts"] }),
  });
}

/** Approved payouts waiting for the next batch — the disburse button's label. */
export function useDisbursementQueueQuery() {
  return useQuery({
    queryKey: financeKeys.disbursementQueue(),
    queryFn: async () => (await payoutService.disbursementQueue()).data ?? null,
  });
}

export function useDisburseMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => payoutService.disburse(),
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
