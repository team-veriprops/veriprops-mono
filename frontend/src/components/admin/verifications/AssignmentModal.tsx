"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@3rdparty/ui/dialog";
import { Button } from "@3rdparty/ui/button";
import { useAvailableAgents, useAssignTaskMutation } from "../libs/useAdminQueries";
import type { AvailableAgent, TaskRole } from "../libs/admin-service";
import { getErrorMessage } from "@lib/utils";
import { CheckCircle2 } from "lucide-react";

interface Props {
  vid: string;
  role: TaskRole;
  open: boolean;
  onClose: () => void;
}

export default function AssignmentModal({ vid, role, open, onClose }: Props) {
  const { data, isLoading } = useAvailableAgents({ role });
  const assign = useAssignTaskMutation();
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const agents: AvailableAgent[] = (data as any)?.data ?? [];

  const handleAssign = async () => {
    if (!selected) { setError("Please select an agent"); return; }
    try {
      await assign.mutateAsync({ vid, role, agentId: selected });
      onClose();
      setSelected(null);
      setError(null);
    } catch (e) {
      setError(getErrorMessage(e as Error));
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Assign {role} Agent</DialogTitle>
        </DialogHeader>

        {isLoading ? (
          <div className="py-6 text-center text-gray-500">Loading agents…</div>
        ) : agents.length === 0 ? (
          <div className="py-6 text-center text-gray-500">
            No approved agents available for this role.
          </div>
        ) : (
          <div className="space-y-2 max-h-72 overflow-y-auto">
            {agents.map((agent) => (
              <button
                key={agent.agentId}
                onClick={() => setSelected(agent.agentId)}
                style={{ cursor: "pointer" }}
                className={`w-full flex items-center justify-between rounded-lg border px-4 py-3 text-sm transition-colors text-left ${
                  selected === agent.agentId
                    ? "border-indigo-500 bg-indigo-50"
                    : "border-gray-200 hover:border-indigo-300 bg-white"
                }`}
              >
                <div>
                  <p className="font-medium text-gray-900">
                    {agent.firstName} {agent.lastName}
                    {agent.isTrusted && (
                      <span className="ml-2 text-xs text-green-600 font-normal">✓ Trusted</span>
                    )}
                  </p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {agent.coverageStates.join(", ") || "No coverage set"} ·{" "}
                    {agent.activeTaskCount} active task{agent.activeTaskCount !== 1 ? "s" : ""}
                  </p>
                </div>
                {selected === agent.agentId && (
                  <CheckCircle2 className="h-4 w-4 text-indigo-600 flex-shrink-0" />
                )}
              </button>
            ))}
          </div>
        )}

        {error && <p className="text-sm text-red-600">{error}</p>}

        <DialogFooter>
          <Button variant="outline" style={{ cursor: "pointer" }} onClick={onClose}>
            Cancel
          </Button>
          <Button
            style={{ cursor: "pointer" }}
            disabled={!selected || assign.isPending}
            onClick={handleAssign}
          >
            {assign.isPending ? "Assigning…" : "Assign Agent"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
