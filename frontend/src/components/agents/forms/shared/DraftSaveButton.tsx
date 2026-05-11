"use client";

import { useSaveDraftMutation } from "../../libs/useAgentTaskQueries";
import { Save } from "lucide-react";

interface Props {
  taskId: string;
  getPayload: () => Record<string, unknown>;
}

export default function DraftSaveButton({ taskId, getPayload }: Props) {
  const save = useSaveDraftMutation();

  return (
    <button
      type="button"
      disabled={save.isPending}
      style={{ cursor: save.isPending ? "wait" : "pointer" }}
      onClick={() => save.mutate({ taskId, payload: getPayload() })}
      className="flex items-center gap-1.5 px-3 py-1.5 border border-gray-300 rounded text-sm text-gray-700 hover:bg-gray-50 transition-colors disabled:opacity-60"
    >
      <Save className="h-3.5 w-3.5" />
      {save.isPending ? "Saving…" : save.isSuccess ? "Saved ✓" : "Save Draft"}
    </button>
  );
}
