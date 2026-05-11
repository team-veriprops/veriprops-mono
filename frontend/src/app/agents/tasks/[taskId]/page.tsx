"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useTask, useDeclineTaskMutation } from "@components/agents/libs/useAgentTaskQueries";
import FieldAgentForm from "@components/agents/forms/FieldAgentForm";
import SurveyorForm from "@components/agents/forms/SurveyorForm";
import RegistryAgentForm from "@components/agents/forms/RegistryAgentForm";
import LawyerForm from "@components/agents/forms/LawyerForm";
import EscalationModal from "@components/agents/forms/shared/EscalationModal";
import type { Task } from "@components/agents/libs/agent-service";
import { ROUTES } from "@/lib/routes";
import { getErrorMessage } from "@lib/utils";
import { ArrowLeft, AlertTriangle } from "lucide-react";

interface Props {
  params: { taskId: string };
}

const ROLE_LABELS: Record<string, string> = {
  FIELD: "Field Agent Report",
  SURVEYOR: "Surveyor Report",
  REGISTRY: "Registry Report",
  LAWYER: "Legal Opinion",
};

export default function TaskDetailPage({ params }: Props) {
  const router = useRouter();
  const { data, isLoading } = useTask(params.taskId);
  const decline = useDeclineTaskMutation();
  const [escalationOpen, setEscalationOpen] = useState(false);
  const [declineError, setDeclineError] = useState<string | null>(null);

  const task: Task | null = (data as any)?.data ?? null;

  if (isLoading) return <div className="p-6 text-center text-gray-400">Loading…</div>;
  if (!task) return <div className="p-6 text-center text-red-600">Task not found.</div>;

  const isActive = ["ACCEPTED", "IN_PROGRESS"].includes(task.status);
  const isSubmitted = ["SUBMITTED", "APPROVED"].includes(task.status);

  const handleDecline = async () => {
    if (!confirm("Decline this task? It will return to the available pool.")) return;
    try {
      await decline.mutateAsync(task.id);
      router.push(ROUTES.AGENT.DASHBOARD);
    } catch (e) {
      setDeclineError(getErrorMessage(e as Error));
    }
  };

  const renderForm = () => {
    if (!isActive) return null;
    switch (task.role) {
      case "FIELD": return <FieldAgentForm task={task} onSubmitted={() => router.push(ROUTES.AGENT.DASHBOARD)} />;
      case "SURVEYOR": return <SurveyorForm task={task} onSubmitted={() => router.push(ROUTES.AGENT.DASHBOARD)} />;
      case "REGISTRY": return <RegistryAgentForm task={task} onSubmitted={() => router.push(ROUTES.AGENT.DASHBOARD)} />;
      case "LAWYER": return <LawyerForm task={task} onSubmitted={() => router.push(ROUTES.AGENT.DASHBOARD)} />;
      default: return null;
    }
  };

  return (
    <div className="p-6 max-w-2xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => router.push(ROUTES.AGENT.DASHBOARD)}
          style={{ cursor: "pointer" }}
          className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700"
        >
          <ArrowLeft className="h-4 w-4" />
          Dashboard
        </button>
        <div className="flex items-center gap-2">
          {isActive && (
            <>
              <button
                onClick={() => setEscalationOpen(true)}
                style={{ cursor: "pointer" }}
                className="flex items-center gap-1.5 text-xs text-orange-600 hover:text-orange-800 border border-orange-200 rounded px-3 py-1.5"
              >
                <AlertTriangle className="h-3 w-3" />
                Report Issue
              </button>
              {task.status === "ACCEPTED" && (
                <button
                  onClick={handleDecline}
                  style={{ cursor: "pointer" }}
                  disabled={decline.isPending}
                  className="text-xs text-gray-500 hover:text-red-600 border border-gray-200 rounded px-3 py-1.5 disabled:opacity-60"
                >
                  {decline.isPending ? "Declining…" : "Decline Task"}
                </button>
              )}
            </>
          )}
        </div>
      </div>

      {/* Task info */}
      <div>
        <h1 className="text-xl font-semibold text-gray-900">{ROLE_LABELS[task.role] ?? task.role}</h1>
        <div className="flex items-center gap-3 mt-1">
          <span className="text-xs text-gray-500 font-mono">
            Verification {task.verificationId.slice(0, 12)}…
          </span>
          <span className="text-xs bg-gray-100 text-gray-700 px-2 py-0.5 rounded">
            {task.status.replace("_", " ")}
          </span>
        </div>
        {declineError && <p className="text-sm text-red-600 mt-2">{declineError}</p>}
      </div>

      {isSubmitted && (
        <div className="rounded-lg border border-green-200 bg-green-50 p-4 text-sm text-green-800">
          ✓ Your report has been submitted and is under review.
        </div>
      )}

      {renderForm()}

      <EscalationModal
        taskId={task.id}
        open={escalationOpen}
        onClose={() => setEscalationOpen(false)}
      />
    </div>
  );
}
