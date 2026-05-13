"use client";

import { useState } from "react";
import { Button } from "@3rdparty/ui/button";
import { useAddNoteMutation } from "../libs/useAdminQueries";
import type { VerificationNote } from "../libs/admin-service";
import { getErrorMessage } from "@lib/utils";
import { Pin } from "lucide-react";

interface Props {
  vid: string;
  notes: VerificationNote[];
}

export default function NotesList({ vid, notes }: Props) {
  const addNote = useAddNoteMutation();
  const [content, setContent] = useState("");
  const [pinned, setPinned] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

  const handleAdd = async () => {
    if (!content.trim()) { setError("Note content is required"); return; }
    try {
      await addNote.mutateAsync({ vid, content, tags: [], pinned });
      setContent("");
      setPinned(false);
      setError(null);
      setAdding(false);
    } catch (e) {
      setError(getErrorMessage(e as Error));
    }
  };

  const sorted = [...notes].sort((a, b) =>
    a.pinned === b.pinned ? 0 : a.pinned ? -1 : 1,
  );

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-700">Notes</h3>
        <button
          style={{ cursor: "pointer" }}
          onClick={() => setAdding((v) => !v)}
          className="text-xs text-indigo-600 hover:text-indigo-800 font-medium"
        >
          {adding ? "Cancel" : "+ Add Note"}
        </button>
      </div>

      {adding && (
        <div className="border rounded-lg p-3 space-y-2 bg-gray-50">
          <textarea
            className="w-full border rounded px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500"
            rows={3}
            placeholder="Write a note…"
            value={content}
            onChange={(e) => setContent(e.target.value)}
          />
          <div className="flex items-center justify-between">
            <label className="flex items-center gap-1.5 text-xs text-gray-600" style={{ cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={pinned}
                onChange={(e) => setPinned(e.target.checked)}
                style={{ cursor: "pointer" }}
              />
              Pin this note
            </label>
            {error && <p className="text-xs text-red-600">{error}</p>}
            <Button
              size="sm"
              style={{ cursor: "pointer" }}
              disabled={addNote.isPending}
              onClick={handleAdd}
            >
              {addNote.isPending ? "Saving…" : "Save Note"}
            </Button>
          </div>
        </div>
      )}

      {sorted.length === 0 ? (
        <p className="text-xs text-gray-400 italic">No notes yet.</p>
      ) : (
        <div className="space-y-2">
          {sorted.map((note) => (
            <div
              key={note.id}
              className={`rounded-lg border p-3 text-sm ${
                note.pinned ? "border-yellow-300 bg-yellow-50" : "border-gray-200 bg-white"
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <p className="text-gray-800 flex-1">{note.content}</p>
                {note.pinned && (
                  <Pin className="h-3.5 w-3.5 text-yellow-500 flex-shrink-0 mt-0.5" />
                )}
              </div>
              <p className="text-xs text-gray-400 mt-1">
                {new Date(note.dateCreated).toLocaleString()}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
