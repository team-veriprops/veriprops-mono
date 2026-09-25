import { describe, it, expect, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { TaskState } from "@/types/adminVerification";
import { AgentRole } from "@/types/agent";
import { VerificationTier } from "@/types/verification";
import { AgentTask } from "@/types/agentTask";
import { Page } from "@/types/models";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {} }) }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const noopMutation = { mutateAsync: vi.fn(), isPending: false };
const listResult: { data: Page<AgentTask> | null; isLoading: boolean; isError: boolean } = {
  data: null,
  isLoading: false,
  isError: false,
};

vi.mock("./libs/useAgentTaskQueries", () => ({
  useAgentTasksQuery: () => listResult,
  useAcceptTaskMutation: () => noopMutation,
  useDeclineTaskMutation: () => noopMutation,
}));

import AgentTaskList from "./AgentTaskList";

function pageOf(items: AgentTask[]): Page<AgentTask> {
  return {
    status: "success",
    code: "200",
    items,
    meta: { page: 0, pageSize: 10, count: items.length, total: items.length, totalPages: 1 },
  };
}

const task: AgentTask = {
  id: "task-1",
  verificationId: "abcdef1234567890",
  role: AgentRole.FIELD,
  tier: VerificationTier.STANDARD,
  state: TaskState.IN_PROGRESS,
  inPool: false,
  evidenceCount: 2,
} as AgentTask;

describe("AgentTaskList", () => {
  it("humanizes role, state, and tier — never rendering raw enum strings", () => {
    listResult.data = pageOf([task]);
    const html = renderToStaticMarkup(<AgentTaskList />);
    expect(html).toContain("Field");
    expect(html).toContain("In Progress");
    expect(html).toContain("agent-task-task-1");
    expect(html).not.toContain("IN_PROGRESS");
    expect(html).not.toContain(">FIELD<");
  });

  /**
   * A manually assigned task is out of the pool and sitting in ASSIGNED, waiting for this
   * agent to take it (§2.2). The list is where they see it first, so the accept control
   * belongs here too — not only on open-pool tasks.
   */
  it("offers accept on an admin-assigned task, not only on open-pool tasks", () => {
    listResult.data = pageOf([{ ...task, state: TaskState.ASSIGNED }]);
    const html = renderToStaticMarkup(<AgentTaskList />);
    expect(html).toContain("accept-task-1");
  });

  it("renders a friendly empty state when there are no tasks", () => {
    listResult.data = pageOf([]);
    const html = renderToStaticMarkup(<AgentTaskList />);
    expect(html).toContain("No tasks assigned yet");
  });
});
