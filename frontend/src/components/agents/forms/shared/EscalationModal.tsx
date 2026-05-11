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
import { useReportEscalationMutation } from "../../libs/useAgentTaskQueries";
import type { Escalation } from "../../libs/agent-service";
import { getErrorMessage } from "@lib/utils";
import { AlertTriangle } from "lucide-react";

const CATEGORIES: Array<{ value: Escalation["category"]; label: string }> = [
  { value: "INACCESSIBLE", label: "Property inaccessible" },
  { value: "SUSPICIOUS", label: "Suspicious activity" },
  { value: "SAFETY", label: "Safety concern" },
  { value: "CONFLICTING", label: "Conflicting information" },
  { value: "OTHER", label: "Other issue" },
];

interface Props {
  taskId: string;
  open: boolean;
  onClose: () => void;
}

export default function EscalationModal({ taskId, open, onClose }: Props) {
  const report = useReportEscalationMutation();
  const [category, setCategory] = useState<Escalation["category"]>("OTHER");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (description.trim().length < 20) {
      setError("Please provide at least 20 characters describing the issue.");
      return;
    }
    try {
      await report.mutateAsync({ taskId, category, description });
      onClose();
      setDescription("");
      setError(null);
    } catch (e) {
      setError(getErrorMessage(e as Error));
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-orange-500" />
            Report an Issue
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Issue Type</label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value as Escalation["category"])}
              style={{ cursor: "pointer" }}
              className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400"
            >
              {CATEGORIES.map((c) => (
                <option key={c.value} value={c.value}>{c.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Description <span className="text-red-500">*</span>
            </label>
            <textarea
              rows={4}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe the issue in detail…"
              className="w-full border rounded px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-orange-400"
            />
            <p className="text-xs text-gray-400 mt-1">{description.length} chars (min 20)</p>
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
        </div>
        <DialogFooter>
          <Button variant="outline" style={{ cursor: "pointer" }} onClick={onClose}>Cancel</Button>
          <Button
            style={{ cursor: "pointer" }}
            disabled={report.isPending}
            onClick={handleSubmit}
            className="bg-orange-600 hover:bg-orange-700 text-white"
          >
            {report.isPending ? "Reporting…" : "Submit Report"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
