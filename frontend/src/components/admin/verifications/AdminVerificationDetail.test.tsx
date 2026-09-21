import { describe, it, expect, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { AgentRole } from "@/types/agent";
import { VerificationStatus, VerificationTier } from "@/types/verification";
import { SlaHealth, TaskState, VerificationDetail } from "@/types/adminVerification";
import { attributeFor, isNamed } from "@/test-utils/markup";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {} }) }));
vi.mock("@components/3rdparty/ui/use-toast", () => ({ toast: () => {} }));

const noopMutation = { mutateAsync: vi.fn(), mutate: vi.fn(), isPending: false };
const detailResult: { data: VerificationDetail | null; isLoading: boolean; isError: boolean } = {
  data: null,
  isLoading: false,
  isError: false,
};

vi.mock("@components/agents/reputation/libs/useReputationQueries", () => ({
  useSuggestedAgentsQuery: () => ({ data: [], isLoading: false }),
}));

vi.mock("./libs/useAdminVerificationQueries", () => ({
  useAdminVerificationDetailQuery: () => detailResult,
  useAssignAgentMutation: () => noopMutation,
  useAddNoteMutation: () => noopMutation,
  useCancelMutation: () => noopMutation,
  usePauseMutation: () => noopMutation,
  useResumeMutation: () => noopMutation,
  useSetDelayMutation: () => noopMutation,
  useResolveChargebackMutation: () => noopMutation,
  useSubmitRebuttalMutation: () => noopMutation,
}));

import AdminVerificationDetail from "./AdminVerificationDetail";

const detail: VerificationDetail = {
  summary: {
    id: "v1",
    vid: "VP-2026-TEST01",
    customerId: "c1",
    tier: VerificationTier.STANDARD,
    status: VerificationStatus.PAID,
    paused: false,
    slaDueDate: "2026-09-25",
    slaHealth: SlaHealth.ON_TRACK,
    dateCreated: "2026-09-16",
  },
  tasks: [
    {
      id: "t1",
      verificationId: "v1",
      role: AgentRole.FIELD,
      tier: VerificationTier.STANDARD,
      state: TaskState.PENDING,
      inPool: false,
      declineCount: 0,
    },
  ],
  notes: [],
  payments: [],
  commissions: [],
  chargebacks: [],
  progressPercent: 0,
  requiredTaskCount: 3,
  approvedTaskCount: 0,
};

function markup(): string {
  detailResult.data = detail;
  return renderToStaticMarkup(<AdminVerificationDetail verificationId="v1" />);
}

/**
 * Admins run this console all day, and several of its controls shipped with a label that sits
 * beside the control without naming it — which is nothing at all to a screen reader.
 */
describe("AdminVerificationDetail", () => {
  it("binds the SLA-extension field to its label", () => {
    expect(isNamed(markup(), "delay-days")).toBe(true);
  });

  it("names the note-category select", () => {
    // A Radix trigger is a <button> with no text of its own until a value is chosen, so it
    // carries its own name (axe `button-name`, critical).
    expect(attributeFor(markup(), "note-category", "aria-label")).toBeTruthy();
  });

  it("names the task-progress bar", () => {
    // The surrounding text says "0/3 approved", but the progressbar node itself is what
    // assistive tech announces (axe `aria-progressbar-name`).
    expect(attributeFor(markup(), "task-progress", "aria-label")).toBeTruthy();
  });
});
