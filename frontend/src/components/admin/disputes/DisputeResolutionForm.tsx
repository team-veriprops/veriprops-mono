"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@3rdparty/ui/dialog";
import { Button } from "@3rdparty/ui/button";
import { httpClient } from "@/containers";
import { getErrorMessage } from "@lib/utils";

type Outcome = "REJECTED" | "FULL_REFUND" | "PARTIAL_RECHECK";

const OUTCOMES: { value: Outcome; label: string; desc: string }[] = [
  { value: "REJECTED", label: "Reject Dispute", desc: "Mark the dispute as unfounded; verification returns to COMPLETED." },
  { value: "FULL_REFUND", label: "Full Refund", desc: "Refund the customer fully; verification marked REFUNDED." },
  { value: "PARTIAL_RECHECK", label: "Partial Re-check", desc: "Initiate a new verification cycle for affected scope." },
];

interface Props {
  disputeId: string;
  open: boolean;
  onClose: () => void;
}

export default function DisputeResolutionForm({ disputeId, open, onClose }: Props) {
  const qc = useQueryClient();
  const [outcome, setOutcome] = useState<Outcome>("REJECTED");
  const [resolutionNote, setResolutionNote] = useState("");
  const [error, setError] = useState<string | null>(null);

  const resolve = useMutation({
    mutationFn: () =>
      httpClient.post(`/api/admin/disputes/${disputeId}/resolve`, { outcome, resolutionNote }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "disputes"] });
      setError(null);
      onClose();
    },
    onError: (e: any) => setError(getErrorMessage(e)),
  });

  const handleClose = () => {
    setOutcome("REJECTED");
    setResolutionNote("");
    setError(null);
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent data-testid="dispute-resolution-form">
        <DialogHeader>
          <DialogTitle>Resolve Dispute</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            {OUTCOMES.map((o) => (
              <label
                key={o.value}
                style={{ cursor: "pointer" }}
                className={`flex items-start gap-3 rounded-md border p-3 transition-colors ${
                  outcome === o.value ? "border-indigo-400 bg-indigo-50" : "border-gray-200 hover:bg-gray-50"
                }`}
                data-testid={`dispute-outcome-${o.value}`}
              >
                <input
                  type="radio"
                  name="outcome"
                  value={o.value}
                  checked={outcome === o.value}
                  onChange={() => setOutcome(o.value)}
                  className="mt-0.5"
                />
                <div>
                  <p className="text-sm font-medium text-gray-900">{o.label}</p>
                  <p className="text-xs text-gray-500">{o.desc}</p>
                </div>
              </label>
            ))}
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Resolution Note</label>
            <textarea
              rows={3}
              value={resolutionNote}
              onChange={(e) => setResolutionNote(e.target.value)}
              placeholder="Provide a note explaining the resolution decision…"
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500"
              data-testid="dispute-resolution-note"
            />
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
        </div>
        <DialogFooter>
          <Button variant="outline" style={{ cursor: "pointer" }} onClick={handleClose}>
            Cancel
          </Button>
          <Button
            style={{ cursor: "pointer" }}
            disabled={resolve.isPending}
            onClick={() => resolve.mutate()}
            data-testid="dispute-resolve-submit-button"
          >
            {resolve.isPending ? "Resolving…" : "Resolve Dispute"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
