"use client";

import { useState } from "react";
import { Button } from "@3rdparty/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@3rdparty/ui/dialog";
import {
  usePauseVerificationMutation,
  useResumeVerificationMutation,
  useCancelVerificationMutation,
  useFailVerificationMutation,
  useReleaseToPoolMutation,
} from "../libs/useAdminQueries";
import type { AdminVerificationDetail } from "../libs/admin-service";
import { getErrorMessage } from "@lib/utils";

interface Props {
  verification: AdminVerificationDetail;
}

export default function AdminActionPanel({ verification }: Props) {
  const { vid, status } = verification;
  const pause = usePauseVerificationMutation();
  const resume = useResumeVerificationMutation();
  const cancel = useCancelVerificationMutation();
  const fail = useFailVerificationMutation();
  const releaseToPool = useReleaseToPoolMutation();

  const [failDialog, setFailDialog] = useState(false);
  const [failReason, setFailReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const handleFail = async () => {
    if (!failReason.trim()) { setError("Reason is required"); return; }
    try {
      await fail.mutateAsync({ vid, reason: failReason });
      setFailDialog(false);
      setFailReason("");
      setError(null);
    } catch (e) {
      setError(getErrorMessage(e as Error));
    }
  };

  const active = ["PAID", "IN_PROGRESS", "UNDER_REVIEW"].includes(status);
  const canPause = status === "IN_PROGRESS";
  const canResume = status === "PAUSED";
  const canRelease = status === "PAID";

  return (
    <>
      <div className="flex flex-wrap gap-2">
        {canPause && (
          <Button
            size="sm"
            variant="outline"
            style={{ cursor: "pointer" }}
            disabled={pause.isPending}
            onClick={() => pause.mutate(vid)}
          >
            {pause.isPending ? "Pausing…" : "Pause"}
          </Button>
        )}
        {canResume && (
          <Button
            size="sm"
            variant="outline"
            style={{ cursor: "pointer" }}
            disabled={resume.isPending}
            onClick={() => resume.mutate(vid)}
          >
            {resume.isPending ? "Resuming…" : "Resume"}
          </Button>
        )}
        {canRelease && (
          <Button
            size="sm"
            variant="outline"
            style={{ cursor: "pointer" }}
            disabled={releaseToPool.isPending}
            onClick={() => releaseToPool.mutate(vid)}
          >
            {releaseToPool.isPending ? "Releasing…" : "Release to Pool"}
          </Button>
        )}
        {active && (
          <>
            <Button
              size="sm"
              variant="outline"
              style={{ cursor: "pointer" }}
              disabled={cancel.isPending}
              onClick={() => cancel.mutate(vid)}
              className="text-orange-600 border-orange-300 hover:bg-orange-50"
            >
              {cancel.isPending ? "Cancelling…" : "Cancel"}
            </Button>
            <Button
              size="sm"
              variant="outline"
              style={{ cursor: "pointer" }}
              onClick={() => setFailDialog(true)}
              className="text-red-600 border-red-300 hover:bg-red-50"
            >
              Fail
            </Button>
          </>
        )}
      </div>

      <Dialog open={failDialog} onOpenChange={setFailDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Fail Verification</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <label className="block text-sm font-medium text-gray-700">
              Reason <span className="text-red-500">*</span>
            </label>
            <textarea
              className="w-full border rounded px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-red-500"
              rows={4}
              placeholder="Describe why this verification is being failed…"
              value={failReason}
              onChange={(e) => setFailReason(e.target.value)}
            />
            {error && <p className="text-sm text-red-600">{error}</p>}
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              style={{ cursor: "pointer" }}
              onClick={() => setFailDialog(false)}
            >
              Cancel
            </Button>
            <Button
              style={{ cursor: "pointer" }}
              disabled={fail.isPending}
              onClick={handleFail}
              className="bg-red-600 hover:bg-red-700 text-white"
            >
              {fail.isPending ? "Failing…" : "Confirm Fail"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
