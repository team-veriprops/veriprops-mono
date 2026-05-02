"use client";

import { useAgentApplication } from "@components/agents/libs/useAgentApplicationQueries";
import ApprovalStatusCard from "@components/agents/onboarding/ApprovalStatusCard";

export default function AgentOnboardingStatusPage() {
  const { data: application, isLoading } = useAgentApplication();

  if (isLoading || !application) {
    return (
      <div
        className="text-sm py-12 text-center"
        style={{ color: "var(--brand-on-surface-variant)" }}
      >
        Loading…
      </div>
    );
  }
  return (
    <div className="max-w-3xl mx-auto px-4 py-10">
      <ApprovalStatusCard application={application} />
    </div>
  );
}
