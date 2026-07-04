"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { httpClient } from "@/containers";
import { AgentRole } from "@/types/agent";
import { VerificationTier } from "@/types/verification";
import { ReviewService, TrustWeightService } from "./review-service";

const reviewService = new ReviewService(httpClient);
const weightService = new TrustWeightService(httpClient);

export const reviewKeys = {
  review: (id: string) => ["admin", "review", id] as const,
  weights: () => ["admin", "trust-weights"] as const,
};

export function useReviewQuery(verificationId: string) {
  return useQuery({
    queryKey: reviewKeys.review(verificationId),
    queryFn: async () => (await reviewService.getReview(verificationId)).data ?? null,
    enabled: !!verificationId,
  });
}

/** Every review mutation returns the fresh review state; seed the cache from it. */
function useReviewMutation<TArgs>(
  fn: (args: TArgs) => Promise<{ data?: unknown }>,
  verificationId: string,
) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (res) => {
      if (res.data) qc.setQueryData(reviewKeys.review(verificationId), res.data);
      qc.invalidateQueries({ queryKey: ["admin", "verifications"] });
    },
  });
}

export function useApproveTaskMutation(verificationId: string) {
  return useReviewMutation(
    ({ role, quality }: { role: AgentRole; quality: number }) =>
      reviewService.approveTask(verificationId, role, quality),
    verificationId,
  );
}

export function useRejectTaskMutation(verificationId: string) {
  return useReviewMutation(
    ({ role, reason }: { role: AgentRole; reason: string }) =>
      reviewService.rejectTask(verificationId, role, reason),
    verificationId,
  );
}

export function useReopenTaskMutation(verificationId: string) {
  return useReviewMutation(
    ({ role }: { role: AgentRole }) => reviewService.reopenTask(verificationId, role),
    verificationId,
  );
}

export function useReleaseMutation(verificationId: string) {
  return useReviewMutation(
    ({ reason }: { reason?: string }) => reviewService.release(verificationId, reason),
    verificationId,
  );
}

export function useFailMutation(verificationId: string) {
  return useReviewMutation(
    ({ reason }: { reason: string }) => reviewService.fail(verificationId, reason),
    verificationId,
  );
}

// ── Trust Score Weights ──
export function useTrustWeightsQuery() {
  return useQuery({
    queryKey: reviewKeys.weights(),
    queryFn: async () => (await weightService.list()).data ?? [],
  });
}

export function useSetTierWeightsMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ tier, weights }: { tier: VerificationTier; weights: Record<AgentRole, number> }) =>
      weightService.setTierWeights(tier, weights),
    onSuccess: () => qc.invalidateQueries({ queryKey: reviewKeys.weights() }),
  });
}

export { reviewService, weightService };
