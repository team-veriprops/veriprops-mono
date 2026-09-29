import { describe, it, expect, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { AgentRole } from "@/types/agent";
import { VerificationStatus, VerificationTier } from "@/types/verification";
import { ReviewDecision, TaskDto, TaskState } from "@/types/adminVerification";
import { ReviewState } from "@/types/adminReview";
import { isNamed } from "@/test-utils/markup";

vi.mock("sonner", () => ({ toast: { success: vi.fn(), warning: vi.fn(), error: vi.fn() } }));

const noopMutation = { mutateAsync: vi.fn(), mutate: vi.fn(), isPending: false };
const reviewResult: { data: ReviewState | null; isLoading: boolean; isError: boolean } = {
  data: null,
  isLoading: false,
  isError: false,
};

vi.mock("./libs/useReviewQueries", () => ({
  useReviewQuery: () => reviewResult,
  useApproveTaskMutation: () => noopMutation,
  useRejectTaskMutation: () => noopMutation,
  useReopenTaskMutation: () => noopMutation,
  useReleaseMutation: () => noopMutation,
  useFailMutation: () => noopMutation,
}));

import AdminReportReview, { failSummary } from "./AdminReportReview";

const review: ReviewState = {
  verificationId: "v1",
  status: VerificationStatus.UNDER_REVIEW,
  tier: VerificationTier.STANDARD,
  tasks: [
    {
      id: "t1",
      verificationId: "v1",
      role: AgentRole.FIELD,
      tier: VerificationTier.STANDARD,
      state: TaskState.SUBMITTED,
      inPool: false,
      declineCount: 0,
    },
  ],
  conflicts: [],
  allApproved: false,
  releasable: false,
  findings: {},
};

function markup(task: Partial<TaskDto> = {}): string {
  reviewResult.data = { ...review, tasks: [{ ...review.tasks[0], ...task }] };
  return renderToStaticMarkup(<AdminReportReview verificationId="v1" />);
}

describe("AdminReportReview", () => {
  /**
   * Approving deliberately leaves the task SUBMITTED until release (§8.3), so the decision
   * badge is the only feedback an admin gets that their review landed.
   */
  it("shows that an approved task was approved, though its state stays submitted", () => {
    const html = markup({ reviewDecision: ReviewDecision.APPROVED });

    expect(html).toContain("Approved");
    expect(html).toContain("Submitted");
  });

  /**
   * The findings block is capped in height and scrolls its overflow, which a phone viewport
   * reaches long before a desktop one. A scrollable region with nothing focusable inside it
   * is unreachable by keyboard (axe `scrollable-region-focusable`), so it takes focus itself.
   */
  it("lets a keyboard reach the findings it has to scroll", () => {
    reviewResult.data = {
      ...review,
      findings: { [AgentRole.FIELD]: { occupancy_status: "VACANT" } },
    };
    const html = renderToStaticMarkup(<AdminReportReview verificationId="v1" />);

    expect(html).toContain("occupancy_status");
    expect(html).toMatch(/<pre[^>]*tabindex="0"/i);
    expect(html).toMatch(/<pre[^>]*aria-label="[^"]+"/i);
  });

  it("binds the quality score to its label", () => {
    // "Quality (0-100)" sits above the box but named nothing: the number an admin types here
    // feeds the composite trust score, so the field has to say what it is.
    expect(isNamed(markup(), `quality-${AgentRole.FIELD}`)).toBe(true);
  });
});

describe("failSummary", () => {
  it("says refunded only when the gateway took the refund", () => {
    expect(failSummary({ refundedMinor: 1_500_000, failedPaymentIds: [], heldPaymentIds: [] })).toEqual({
      ok: true,
      message: "Verification failed & refunded",
    });
  });

  it("says so when a gateway refused the refund, and where it waits", () => {
    const summary = failSummary({ refundedMinor: 0, failedPaymentIds: ["p1"], heldPaymentIds: [] });
    expect(summary.ok).toBe(false);
    expect(summary.message).toMatch(/refused the refund/);
    expect(summary.message).toMatch(/Finance/);
  });

  it("says a refund was held back for a chargeback, which returns the money instead", () => {
    const summary = failSummary({ refundedMinor: 0, failedPaymentIds: [], heldPaymentIds: ["p1"] });
    expect(summary.ok).toBe(false);
    expect(summary.message).toMatch(/chargeback/);
  });

  it("claims nothing when the response carried no refund", () => {
    expect(failSummary(undefined)).toEqual({ ok: true, message: "Verification failed" });
  });
});
