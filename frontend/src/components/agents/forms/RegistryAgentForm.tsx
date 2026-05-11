"use client";

import { useState } from "react";
import { useSubmitTaskMutation } from "../libs/useAgentTaskQueries";
import type { Task } from "../libs/agent-service";
import DeclarationSection from "./shared/DeclarationSection";
import DraftSaveButton from "./shared/DraftSaveButton";
import { getErrorMessage } from "@lib/utils";

interface Props {
  task: Task;
  onSubmitted?: () => void;
}

export default function RegistryAgentForm({ task, onSubmitted }: Props) {
  const submit = useSubmitTaskMutation();
  const draft = task.draftPayload as Record<string, unknown> | null;

  const [registrySearchRef, setRegistrySearchRef] = useState(String(draft?.registry_search_ref ?? ""));
  const [titleDocAssessment, setTitleDocAssessment] = useState(String(draft?.title_doc_assessment ?? ""));
  const [ownershipChain, setOwnershipChain] = useState(String(draft?.ownership_chain ?? ""));
  const [declarationSigned, setDeclarationSigned] = useState(Boolean(draft?.declaration_signed));
  const [error, setError] = useState<string | null>(null);

  const getPayload = () => ({
    registry_search_ref: registrySearchRef,
    title_doc_assessment: titleDocAssessment,
    ownership_chain: ownershipChain,
    declaration_signed: declarationSigned,
  });

  const handleSubmit = async () => {
    if (!registrySearchRef.trim()) { setError("Registry search reference is required."); return; }
    if (!titleDocAssessment.trim()) { setError("Title document assessment is required."); return; }
    if (!ownershipChain.trim()) { setError("Ownership chain is required."); return; }
    if (!declarationSigned) { setError("You must accept the declaration."); return; }
    try {
      await submit.mutateAsync({ taskId: task.id, payload: getPayload() });
      onSubmitted?.();
    } catch (e) {
      setError(getErrorMessage(e as Error));
    }
  };

  return (
    <div className="space-y-5">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Registry Search Reference <span className="text-red-500">*</span>
        </label>
        <input
          type="text"
          value={registrySearchRef}
          onChange={(e) => setRegistrySearchRef(e.target.value)}
          placeholder="e.g. REG-2024-XXXXXX"
          className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Title Document Assessment <span className="text-red-500">*</span>
        </label>
        <textarea
          rows={4}
          value={titleDocAssessment}
          onChange={(e) => setTitleDocAssessment(e.target.value)}
          placeholder="Assess the authenticity and validity of the title document…"
          className="w-full border rounded px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Ownership Chain <span className="text-red-500">*</span>
        </label>
        <textarea
          rows={4}
          value={ownershipChain}
          onChange={(e) => setOwnershipChain(e.target.value)}
          placeholder="Describe the chain of ownership from original grant to current owner…"
          className="w-full border rounded px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
      </div>

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
          {submit.isPending ? "Submitting…" : "Submit Registry Report"}
        </button>
      </div>
    </div>
  );
}
