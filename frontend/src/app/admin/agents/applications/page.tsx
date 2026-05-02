import AgentApplicationsQueue from "@components/admin/agents/AgentApplicationsQueue";

export const metadata = {
  title: "Agent applications — Veriprops Admin",
};

export default function AdminAgentApplicationsPage() {
  return (
    <div className="max-w-6xl mx-auto px-4 py-10">
      <AgentApplicationsQueue />
    </div>
  );
}
