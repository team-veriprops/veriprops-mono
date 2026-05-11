"use client";

import { useState } from "react";
import { useSubmitTaskMutation } from "../libs/useAgentTaskQueries";
import type { Task } from "../libs/agent-service";
import EvidenceUploadSection from "./shared/EvidenceUploadSection";
import DeclarationSection from "./shared/DeclarationSection";
import DraftSaveButton from "./shared/DraftSaveButton";
import { getErrorMessage } from "@lib/utils";

interface Props {
  task: Task;
  onSubmitted?: () => void;
}

export default function FieldAgentForm({ task, onSubmitted }: Props) {
  const submit = useSubmitTaskMutation();
  const draft = task.draftPayload as Record<string, unknown> | null;

  const [accessConfirmed, setAccessConfirmed] = useState<boolean>(
    Boolean(draft?.access_confirmed),
  );
  const [conditions, setConditions] = useState<string>(
    String(draft?.conditions ?? ""),
  );
  const [observations, setObservations] = useState<string>(
    String(draft?.observations ?? ""),
  );
  const [declarationSigned, setDeclarationSigned] = useState<boolean>(
    Boolean(draft?.declaration_signed),
  );
  const [uploadedCount] = useState<number>(0);
  const [error, setError] = useState<string | null>(null);

  const getPayload = () => ({
    access_confirmed: accessConfirmed,
    conditions,
    observations,
    declaration_signed: declarationSigned,
  });

  const handleSubmit = async () => {
    if (!accessConfirmed) { setError("Please confirm access to the property."); return; }
    if (!declarationSigned) { setError("You must accept the declaration before submitting."); return; }
    try {
      await submit.mutateAsync({ taskId: task.id, payload: getPayload() });
      onSubmitted?.();
    } catch (e) {
      setError(getErrorMessage(e as Error));
    }
  };

  return (
    <div className="space-y-6">
      {/* Property access */}
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-gray-700">Property Access</h3>
        <label className="flex items-start gap-2" style={{ cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={accessConfirmed}
            onChange={(e) => setAccessConfirmed(e.target.checked)}
            style={{ cursor: "pointer", marginTop: 2 }}
          />
          <span className="text-sm text-gray-700">
            I confirm I physically accessed and inspected the property
            <span className="text-red-500 ml-0.5">*</span>
          </span>
        </label>
      </div>

      {/* Condition checklist */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Property Condition Notes
        </label>
        <textarea
          rows={3}
          value={conditions}
          onChange={(e) => setConditions(e.target.value)}
          placeholder="Describe the overall condition of the property…"
          className="w-full border rounded px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
      </div>

      {/* Observations */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Observations & Neighbourhood
        </label>
        <textarea
          rows={4}
          value={observations}
          onChange={(e) => setObservations(e.target.value)}
          placeholder="Describe neighbourhood, access roads, notable features…"
          className="w-full border rounded px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
      </div>

      {/* Evidence */}
      <EvidenceUploadSection taskId={task.id} minPhotos={5} uploadedCount={uploadedCount} />

      {/* Declaration */}
      <DeclarationSection value={declarationSigned} onChange={setDeclarationSigned} />

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="flex items-center gap-3 pt-2">
        <DraftSaveButton taskId={task.id} getPayload={getPayload} />
        <button
          type="button"
          disabled={submit.isPending}
          style={{ cursor: submit.isPending ? "wait" : "pointer" }}
          onClick={handleSubmit}
          className="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium py-2 rounded transition-colors disabled:opacity-60"
        >
          {submit.isPending ? "Submitting…" : "Submit Report"}
        </button>
      </div>
    </div>
  );
}
