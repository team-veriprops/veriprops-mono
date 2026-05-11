"use client";

import { useState } from "react";
import { useSubmitTaskMutation } from "../libs/useAgentTaskQueries";
import type { Task } from "../libs/agent-service";
import DeclarationSection from "./shared/DeclarationSection";
import DraftSaveButton from "./shared/DraftSaveButton";
import { getErrorMessage } from "@lib/utils";
import { Lock, AlertTriangle } from "lucide-react";

interface Props {
  task: Task;
  siblingStatuses?: Record<string, string>;
  onSubmitted?: () => void;
}

const MIN_OPINION_CHARS = 200;

export default function LawyerForm({ task, siblingStatuses = {}, onSubmitted }: Props) {
  const submit = useSubmitTaskMutation();
  const draft = task.draftPayload as Record<string, unknown> | null;

  const allSiblingsSettled = Object.values(siblingStatuses).every(
    (s) => s === "SUBMITTED" || s === "APPROVED",
  );

  const [legalOpinion, setLegalOpinion] = useState(String(draft?.legal_opinion ?? ""));
  const [recommendation, setRecommendation] = useState<string>(
    String(draft?.recommendation ?? "PROCEED"),
  );
  const [encumbrances, setEncumbrances] = useState(String(draft?.encumbrances ?? ""));
  const [nbaConfirmed, setNbaConfirmed] = useState(Boolean(draft?.nba_confirmed));
  const [declarationSigned, setDeclarationSigned] = useState(Boolean(draft?.declaration_signed));
  const [error, setError] = useState<string | null>(null);

  const opinonLength = legalOpinion.length;
  const opinionOk = opinonLength >= MIN_OPINION_CHARS;

  const getPayload = () => ({
    legal_opinion: legalOpinion,
    recommendation,
    encumbrances,
    nba_confirmed: nbaConfirmed,
    declaration_signed: declarationSigned,
  });

  const handleSubmit = async () => {
    if (!allSiblingsSettled) {
      setError("All other agents must submit before you can submit.");
      return;
    }
    if (!opinionOk) {
      setError(`Legal opinion must be at least ${MIN_OPINION_CHARS} characters (${opinonLength} so far).`);
      return;
    }
    if (!nbaConfirmed) { setError("NBA confirmation is required."); return; }
    if (!declarationSigned) { setError("You must accept the declaration."); return; }
    try {
      await submit.mutateAsync({ taskId: task.id, payload: getPayload() });
      onSubmitted?.();
    } catch (e) {
      setError(getErrorMessage(e as Error));
    }
  };

  if (!allSiblingsSettled) {
    return (
      <div className="rounded-lg border border-orange-200 bg-orange-50 p-6 text-center space-y-3">
        <Lock className="h-8 w-8 text-orange-400 mx-auto" />
        <h3 className="text-sm font-semibold text-orange-800">Waiting for Other Agents</h3>
        <p className="text-xs text-orange-700">
          The field agent, surveyor, and registry agent must all submit their reports before you can
          proceed. Check back once they have completed their work.
        </p>
        <div className="space-y-1 text-left mt-3">
          {Object.entries(siblingStatuses).map(([role, status]) => (
            <div key={role} className="flex items-center justify-between text-xs">
              <span className="text-orange-700">{role}</span>
              <span className={
                ["SUBMITTED", "APPROVED"].includes(status)
                  ? "text-green-600 font-medium"
                  : "text-orange-500"
              }>
                {status}
              </span>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Legal Opinion <span className="text-red-500">*</span>
          <span className="text-xs text-gray-400 ml-2">min {MIN_OPINION_CHARS} chars</span>
        </label>
        <textarea
          rows={8}
          value={legalOpinion}
          onChange={(e) => setLegalOpinion(e.target.value)}
          placeholder="Provide a comprehensive legal opinion on the title, encumbrances, and risks…"
          className={`w-full border rounded px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 ${
            opinionOk ? "focus:ring-indigo-500" : "focus:ring-orange-400 border-orange-300"
          }`}
        />
        <p className={`text-xs mt-1 ${opinionOk ? "text-gray-400" : "text-orange-500"}`}>
          {opinonLength} / {MIN_OPINION_CHARS} characters
        </p>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Encumbrances</label>
        <textarea
          rows={3}
          value={encumbrances}
          onChange={(e) => setEncumbrances(e.target.value)}
          placeholder="List any liens, mortgages, or other encumbrances…"
          className="w-full border rounded px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Recommendation <span className="text-red-500">*</span>
        </label>
        <select
          value={recommendation}
          onChange={(e) => setRecommendation(e.target.value)}
          style={{ cursor: "pointer" }}
          className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          <option value="PROCEED">Proceed — title is clear</option>
          <option value="CAUTION">Proceed with Caution</option>
          <option value="DO_NOT_PROCEED">Do Not Proceed — title defective</option>
        </select>
      </div>

      <label className="flex items-start gap-2" style={{ cursor: "pointer" }}>
        <input
          type="checkbox"
          checked={nbaConfirmed}
          onChange={(e) => setNbaConfirmed(e.target.checked)}
          style={{ cursor: "pointer", marginTop: 2 }}
        />
        <span className="text-sm text-gray-700">
          I confirm I am a licensed member of the Nigerian Bar Association (NBA)
          <span className="text-red-500 ml-0.5">*</span>
        </span>
      </label>

      <DeclarationSection value={declarationSigned} onChange={setDeclarationSigned} />

      {error && (
        <div className="flex items-center gap-2 text-sm text-red-600">
          <AlertTriangle className="h-4 w-4 flex-shrink-0" />
          {error}
        </div>
      )}

      <div className="flex items-center gap-3 pt-2">
        <DraftSaveButton taskId={task.id} getPayload={getPayload} />
        <button
          type="button"
          disabled={submit.isPending}
          style={{ cursor: submit.isPending ? "wait" : "pointer" }}
          onClick={handleSubmit}
          className="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium py-2 rounded transition-colors disabled:opacity-60"
        >
          {submit.isPending ? "Submitting…" : "Submit Legal Opinion"}
        </button>
      </div>
    </div>
  );
}
