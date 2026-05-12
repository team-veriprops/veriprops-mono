"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
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

const ROLES = ["SURVEYOR", "LAWYER", "INSPECTOR", "REGISTRY"];

interface Props {
  verificationId: string;
  open: boolean;
  onClose: () => void;
}

export default function RecheckModal({ verificationId, open, onClose }: Props) {
  const [reason, setReason] = useState("");
  const [scopeRoles, setScopeRoles] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  const submit = useMutation({
    mutationFn: () =>
      httpClient.post(`/portal/verifications/${verificationId}/recheck`, {
        reason,
        scopeRoles,
      }),
    onSuccess: () => {
      setSubmitted(true);
      setError(null);
    },
    onError: (e: any) => setError(getErrorMessage(e)),
  });

  const toggleRole = (role: string) => {
    setScopeRoles((prev) =>
      prev.includes(role) ? prev.filter((r) => r !== role) : [...prev, role]
    );
  };

  const handleClose = () => {
    if (!submitted) {
      setReason("");
      setScopeRoles([]);
      setError(null);
    }
    setSubmitted(false);
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent data-testid="recheck-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <RefreshCw className="h-4 w-4 text-blue-500" />
            Request Re-check
          </DialogTitle>
        </DialogHeader>

        {submitted ? (
          <div className="py-4 text-center">
            <p className="text-green-700 font-medium">Re-check request submitted.</p>
            <p className="text-sm text-gray-500 mt-1">
              An admin will review your request and contact you with pricing details.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Reason for Re-check <span className="text-red-500">*</span>
              </label>
              <textarea
                rows={4}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Describe what needs to be re-checked and why…"
                className="w-full rounded border border-gray-300 px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
                data-testid="recheck-reason-input"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Scope (select roles to re-check)
              </label>
              <div className="flex flex-wrap gap-2">
                {ROLES.map((role) => (
                  <button
                    key={role}
                    type="button"
                    onClick={() => toggleRole(role)}
                    style={{ cursor: "pointer" }}
                    className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                      scopeRoles.includes(role)
                        ? "border-blue-500 bg-blue-50 text-blue-700"
                        : "border-gray-300 text-gray-600 hover:bg-gray-50"
                    }`}
                    data-testid={`recheck-role-${role}`}
                  >
                    {role}
                  </button>
                ))}
              </div>
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
              disabled={submit.isPending || !reason.trim() || scopeRoles.length === 0}
              onClick={() => submit.mutate()}
              data-testid="recheck-submit-button"
            >
              {submit.isPending ? "Submitting…" : "Submit Request"}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
