import { describe, it, expect, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { TaskState } from "@/types/adminVerification";
import { AgentRole } from "@/types/agent";
import { VerificationTier } from "@/types/verification";
import { AgentTask } from "@/types/agentTask";
import { Page } from "@/types/models";
import { attributeFor, isNamed } from "@/test-utils/markup";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {} }) }));
vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => (
    <a href={href}>{children}</a>
  ),
}));
vi.mock("@components/3rdparty/ui/use-toast", () => ({ toast: () => {} }));

const noopMutation = { mutateAsync: vi.fn(), isPending: false };
const listResult: { data: Page<AgentTask> | null; isLoading: boolean; isError: boolean } = {
  data: null,
  isLoading: false,
  isError: false,
};

vi.mock("./libs/useAgentTaskQueries", () => ({
  useAgentTasksQuery: () => listResult,
  useTaskEvidenceQuery: () => ({ data: [] }),
  useAcceptTaskMutation: () => noopMutation,
  useStartTaskMutation: () => noopMutation,
  useUploadEvidenceMutation: () => noopMutation,
  useSubmitTaskMutation: () => noopMutation,
}));

import AgentTaskDetail from "./AgentTaskDetail";

function pageOf(items: AgentTask[]): Page<AgentTask> {
  return {
    status: "success",
    code: "200",
    items,
    meta: { page: 0, pageSize: 100, count: items.length, total: items.length, totalPages: 1 },
  };
}

function taskIn(state: TaskState, extra: Partial<AgentTask> = {}): AgentTask {
  return {
    id: "task-1",
    verificationId: "abcdef1234567890",
    role: AgentRole.FIELD,
    tier: VerificationTier.STANDARD,
    state,
    inPool: false,
    evidenceCount: 1,
    ...extra,
  } as AgentTask;
}

function markupFor(task: AgentTask): string {
  listResult.data = pageOf([task]);
  return renderToStaticMarkup(<AgentTaskDetail taskId={task.id} />);
}

describe("AgentTaskDetail", () => {
  it("offers the accept control while the task is still pending", () => {
    const html = markupFor(taskIn(TaskState.PENDING));
    expect(html).toContain("detail-accept");
    expect(html).not.toContain("detail-start");
  });

  /**
   * The manual-assign path (§2.2) hands a specific agent the work: the task leaves the pool
   * and lands in ASSIGNED, from where the backend's machine allows ASSIGNED → ACCEPTED. The
   * screen has to offer that step, or the agent cannot take a job an admin gave them.
   */
  it("offers the accept control on a task an admin assigned to this agent", () => {
    const html = markupFor(taskIn(TaskState.ASSIGNED));
    expect(html).toContain("detail-accept");
  });

  it("offers the start control once the task is accepted", () => {
    const html = markupFor(taskIn(TaskState.ACCEPTED));
    expect(html).toContain("detail-start");
  });

  /**
   * An admin rejection sends the task to REJECTED, and the backend's task state machine
   * allows REJECTED → IN_PROGRESS — the agent is expected to rework and resubmit. The
   * screen therefore has to offer a way back into the work: without it the agent reads why
   * their submission was returned and can do nothing about it, while the API would have
   * accepted the rework.
   */
  it("lets a rejected task be picked back up, alongside the reason it came back", () => {
    const html = markupFor(
      taskIn(TaskState.REJECTED, { rejectionReason: "The frontage photo is too dark to read." }),
    );

    expect(html).toContain("The frontage photo is too dark to read.");
    expect(html).toContain("detail-rejection-reason");
    // The route back into the work, which REJECTED → IN_PROGRESS is exactly what `start` does.
    expect(html).toContain("detail-start");
  });

  it("collects the role's findings once work is under way", () => {
    const html = markupFor(taskIn(TaskState.IN_PROGRESS));
    expect(html).toContain("field-occupancy_status");
    expect(html).toContain("detail-submit");
  });

  /**
   * Field agents fill this on a phone, often one-handed on site. Every control here shipped
   * with its label merely adjacent, which names nothing for assistive tech.
   */
  it("names the controls an agent works through on site", () => {
    const html = markupFor(taskIn(TaskState.IN_PROGRESS));

    expect(isNamed(html, "field-occupancy_status")).toBe(true);
    expect(isNamed(html, "evidence-file")).toBe(true);
    // A Radix trigger is a <button>, so it carries its own name (axe `button-name`).
    expect(attributeFor(html, "evidence-kind", "aria-label")).toBeTruthy();
  });

  it("tells the agent their submission is with the reviewer", () => {
    const html = markupFor(taskIn(TaskState.SUBMITTED));
    expect(html).toContain("awaiting admin review");
    expect(html).not.toContain("detail-submit");
  });
});
