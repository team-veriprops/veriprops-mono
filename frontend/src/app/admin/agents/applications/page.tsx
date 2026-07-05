import { Suspense } from "react";
import AgentApplicationsAdmin from "@components/admin/agents/AgentApplicationsAdmin";

export default function AdminAgentApplicationsPage() {
  return (
    <div className="p-4 sm:p-6">
      <Suspense>
        <AgentApplicationsAdmin />
      </Suspense>
    </div>
  );
}
