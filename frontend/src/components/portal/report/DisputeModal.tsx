"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { AlertCircle } from "lucide-react";
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

const DISPUTE_TYPES = [
  { value: "INACCURATE_FINDINGS", label: "Inaccurate findings" },
  { value: "MISSING_DOCUMENTS", label: "Missing documents" },
  { value: "AGENT_MISCONDUCT", label: "Agent misconduct" },
  { value: "INCORRECT_PROPERTY_DETAILS", label: "Incorrect property details" },
  { value: "OTHER", label: "Other" },
];

const MIN_DESC_LENGTH = 100;

interface Props {
  verificationId: string;
  open: boolean;
  onClose: () => void;
}

export default function DisputeModal({ verificationId, open, onClose }: Props) {
  const [disputeType, setDisputeType] = useState("INACCURATE_FINDINGS");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  const submit = useMutation({
    mutationFn: () =>
      httpClient.post(`/portal/verifications/${verificationId}/dispute`, {
        disputeType,
        description,
      }),
    onSuccess: () => {
      setSubmitted(true);
      setError(null);
    },
    onError: (e: any) => setError(getErrorMessage(e)),
  });

  const handleClose = () => {
    if (!submitted) {
      setDisputeType("INACCURATE_FINDINGS");
      setDescription("");
      setError(null);
    }
    setSubmitted(false);
    onClose();
  };

  const descTooShort = description.trim().length < MIN_DESC_LENGTH;

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent data-testid="dispute-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4 text-red-500" />
            File a Dispute
          </DialogTitle>
        </DialogHeader>

        {submitted ? (
          <div className="py-4 text-center">
            <p className="text-green-700 font-medium">Dispute submitted successfully.</p>
            <p className="text-sm text-gray-500 mt-1">
              Our team will review your dispute and respond within 3–5 business days.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Dispute Type</label>
              <select
                value={disputeType}
                onChange={(e) => setDisputeType(e.target.value)}
                style={{ cursor: "pointer" }}
                className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-400"
                data-testid="dispute-type-select"
              >
                {DISPUTE_TYPES.map((d) => (
                  <option key={d.value} value={d.value}>{d.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Description <span className="text-red-500">*</span>
              </label>
              <textarea
                rows={5}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe your dispute in detail. Include specific findings you believe are incorrect, and why…"
                className="w-full rounded border border-gray-300 px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-red-400"
                data-testid="dispute-description-input"
              />
              <p className={`text-xs mt-1 ${descTooShort ? "text-red-500" : "text-gray-400"}`}>
                {description.trim().length} / {MIN_DESC_LENGTH} characters minimum
              </p>
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" style={{ cursor: "pointer" }} onClick={handleClose}>
            {submitted ? "Close" : "Cancel"}
          </Button>
          {!submitted && (
            <Button
              style={{ cursor: "pointer" }}
              disabled={submit.isPending || descTooShort}
              onClick={() => submit.mutate()}
              className="bg-red-600 hover:bg-red-700 text-white"
              data-testid="dispute-submit-button"
            >
              {submit.isPending ? "Submitting…" : "Submit Dispute"}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
