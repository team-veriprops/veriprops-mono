import AgentApplicationStatusCard from "@components/agents/dashboard/AgentApplicationStatusCard";

export default function AgentDashboardPage() {
  return (
    <div className="mx-auto w-full max-w-3xl space-y-6 p-4 sm:p-6">
      <h1 className="text-2xl font-bold text-foreground">Agent</h1>
      <AgentApplicationStatusCard />
    </div>
  );
}
