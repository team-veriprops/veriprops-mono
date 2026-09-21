import { describe, it, expect, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { AgentRole } from "@/types/agent";
import { VerificationStatus, VerificationTier } from "@/types/verification";
import { ReviewDecision, TaskDto, TaskState } from "@/types/adminVerification";
import { ReviewState } from "@/types/adminReview";
import { isNamed } from "@/test-utils/markup";

vi.mock("@components/3rdparty/ui/use-toast", () => ({ toast: () => {} }));

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

import AdminReportReview from "./AdminReportReview";

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

  it("binds the quality score to its label", () => {
    // "Quality (0-100)" sits above the box but named nothing: the number an admin types here
    // feeds the composite trust score, so the field has to say what it is.
    expect(isNamed(markup(), `quality-${AgentRole.FIELD}`)).toBe(true);
  });
});
