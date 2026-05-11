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

export default function SurveyorForm({ task, onSubmitted }: Props) {
  const submit = useSubmitTaskMutation();
  const draft = task.draftPayload as Record<string, unknown> | null;

  const [surveyConfirmed, setSurveyConfirmed] = useState(Boolean(draft?.survey_confirmed));
  const [lat, setLat] = useState(String(draft?.boundary_coords_lat ?? ""));
  const [lng, setLng] = useState(String(draft?.boundary_coords_lng ?? ""));
  const [boundaryAssessment, setBoundaryAssessment] = useState(String(draft?.boundary_assessment ?? ""));
  const [surveyPlanRef, setSurveyPlanRef] = useState(String(draft?.survey_plan_ref ?? ""));
  const [declarationSigned, setDeclarationSigned] = useState(Boolean(draft?.declaration_signed));
  const [error, setError] = useState<string | null>(null);

  const getPayload = () => ({
    survey_confirmed: surveyConfirmed,
    boundary_coords: lat && lng ? { lat: parseFloat(lat), lng: parseFloat(lng) } : null,
    boundary_coords_lat: lat,
    boundary_coords_lng: lng,
    boundary_assessment: boundaryAssessment,
    survey_plan_ref: surveyPlanRef,
    declaration_signed: declarationSigned,
  });

  const handleSubmit = async () => {
    if (!surveyConfirmed) { setError("Please confirm the survey was completed."); return; }
    if (!lat || !lng) { setError("Boundary coordinates are required."); return; }
    if (!declarationSigned) { setError("You must accept the declaration."); return; }
    try {
      await submit.mutateAsync({ taskId: task.id, payload: getPayload() });
      onSubmitted?.();
    } catch (e) {
      setError(getErrorMessage(e as Error));
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <label className="flex items-start gap-2" style={{ cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={surveyConfirmed}
            onChange={(e) => setSurveyConfirmed(e.target.checked)}
            style={{ cursor: "pointer", marginTop: 2 }}
          />
          <span className="text-sm text-gray-700">
            I confirm the boundary survey was conducted
            <span className="text-red-500 ml-0.5">*</span>
          </span>
        </label>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Boundary Latitude <span className="text-red-500">*</span>
          </label>
          <input
            type="number"
            step="any"
            value={lat}
            onChange={(e) => setLat(e.target.value)}
            placeholder="e.g. 6.5244"
            className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Boundary Longitude <span className="text-red-500">*</span>
          </label>
          <input
            type="number"
            step="any"
            value={lng}
            onChange={(e) => setLng(e.target.value)}
            placeholder="e.g. 3.3792"
            className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Boundary Assessment</label>
        <textarea
          rows={3}
          value={boundaryAssessment}
          onChange={(e) => setBoundaryAssessment(e.target.value)}
          placeholder="Describe boundary findings, encroachments, discrepancies…"
          className="w-full border rounded px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Survey Plan Reference</label>
        <input
          type="text"
          value={surveyPlanRef}
          onChange={(e) => setSurveyPlanRef(e.target.value)}
          placeholder="Survey plan number or file reference"
          className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
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
          {submit.isPending ? "Submitting…" : "Submit Survey Report"}
        </button>
      </div>
    </div>
  );
}
