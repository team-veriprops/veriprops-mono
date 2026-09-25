import { describe, it, expect, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import { AgentApplicationStatus, AgentApplicationStatusView } from "@/types/agent";
import { UserPersona } from "@components/website/auth/models";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {} }) }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("@components/website/auth/libs/useAuthQueries", () => ({
  authKeys: { session: ["auth", "session"] },
  useRefreshSession: () => async () => {},
}));

const session: { user: { personas: UserPersona[] } } | null = { user: { personas: [] } };
vi.mock("@components/website/auth/libs/useAuthStore", () => ({
  useAuthStore: (select: (s: { session: typeof session }) => unknown) => select({ session }),
}));

const statusResult: { data: AgentApplicationStatusView | null } = { data: null };

vi.mock("@components/agents/libs/useAgentQueries", () => ({
  useAgentDraftQuery: () => ({ data: null }),
  useAgentTermsQuery: () => ({ data: { consentVersion: "1.0.0" } }),
  useAgentStatusQuery: () => statusResult,
  useSaveAgentDraftMutation: () => ({ mutate: vi.fn() }),
  useSubmitAgentApplicationMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

import AgentOnboardingContainer from "./AgentOnboardingContainer";

function markup(closable = false): string {
  return renderToStaticMarkup(<AgentOnboardingContainer closable={closable} />);
}

describe("AgentOnboardingContainer", () => {
  /**
   * A rejected applicant is forced back through this same wizard by the `/agents` layout gate
   * (§3.1). The backend sends the reason on the application status, but nothing agent-facing
   * rendered it — so the only move left to them was to submit the identical application again
   * and be refused again.
   */
  it("tells a rejected applicant why, rather than returning them to a blank form", () => {
    statusResult.data = {
      status: AgentApplicationStatus.REJECTED,
      rejectionReason: "The BVN check did not pass, so we could not confirm your identity.",
      roles: [],
      approvedRoles: [],
      activeRoles: [],
    };

    const html = markup();

    expect(html).toContain("agent-apply-rejection-reason");
    expect(html).toContain("could not confirm your identity");
  });

  it("says nothing about a rejection to a first-time applicant", () => {
    statusResult.data = null;

    expect(markup()).not.toContain("agent-apply-rejection-reason");
  });

  it("keeps the compulsory gate closable=false without a close control", () => {
    statusResult.data = null;

    expect(markup()).not.toContain("agent-apply-close");
  });

  /**
   * On `/agents/apply` the wizard is closable, because a customer can reach it (§3.2 — applying is
   * what grants the agent persona, so the application cannot be gated behind it). Someone who
   * followed "Become an Agent" and changed their mind must be able to leave: the overlay covers
   * the nav, so without this there is no way out but the URL bar.
   */
  it("offers a way out on the application route", () => {
    statusResult.data = null;

    expect(markup(true)).toContain("agent-apply-close");
  });
});
