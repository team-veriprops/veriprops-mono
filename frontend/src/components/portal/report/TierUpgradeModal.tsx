"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowUpCircle, Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@3rdparty/ui/dialog";
import { Button } from "@3rdparty/ui/button";
import { upgradeService } from "./libs/upgrade-service";
import { getErrorMessage } from "@lib/utils";
import { useState } from "react";

interface Props {
  verificationId: string;
  open: boolean;
  onClose: () => void;
}

export default function TierUpgradeModal({ verificationId, open, onClose }: Props) {
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["tier-upgrade-preview", verificationId],
    queryFn: () => upgradeService.preview(verificationId),
    enabled: open,
  });
  const preview = (data as any)?.data;

  const submit = useMutation({
    mutationFn: () => upgradeService.submit(verificationId, preview?.toTier ?? ""),
    onSuccess: () => {
      setSubmitted(true);
      setError(null);
    },
    onError: (e: any) => setError(getErrorMessage(e)),
  });

  const handleClose = () => {
    setSubmitted(false);
    setError(null);
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent data-testid="tier-upgrade-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ArrowUpCircle className="h-4 w-4 text-indigo-500" />
            Upgrade Verification Tier
          </DialogTitle>
        </DialogHeader>

        {isLoading ? (
          <div className="flex justify-center py-6">
            <Loader2 className="h-5 w-5 animate-spin text-indigo-500" />
          </div>
        ) : submitted ? (
          <div className="py-4 text-center">
            <p className="text-green-700 font-medium">Upgrade request submitted.</p>
            <p className="text-sm text-gray-500 mt-1">
              Complete payment to activate the tier upgrade.
            </p>
          </div>
        ) : preview ? (
          <div className="space-y-4">
            <div className="rounded-md border border-gray-200 p-4 bg-gray-50">
              <div className="flex justify-between items-center mb-2">
                <span className="text-sm text-gray-600">Current Tier</span>
                <span className="font-semibold text-gray-900">{preview.fromTier}</span>
              </div>
              <div className="flex justify-between items-center mb-2">
                <span className="text-sm text-gray-600">Upgrade To</span>
                <span className="font-semibold text-indigo-700">{preview.toTier}</span>
              </div>
              <div className="border-t border-gray-200 pt-2 mt-2 flex justify-between items-center">
                <span className="text-sm font-medium text-gray-700">Additional Cost</span>
                <span className="text-lg font-bold text-indigo-700">
                  ₦{preview.deltaPrice.toLocaleString()}
                </span>
              </div>
            </div>
            <p className="text-xs text-gray-500">
              Additional inspections and tasks will be created for the new tier scope. Your current report version will be superseded.
            </p>
            {error && <p className="text-sm text-red-600">{error}</p>}
          </div>
        ) : (
          <p className="text-sm text-gray-500 py-4">
            No upgrade available — you may already be on the highest tier.
          </p>
        )}

        <DialogFooter>
          <Button variant="outline" style={{ cursor: "pointer" }} onClick={handleClose}>
            {submitted ? "Close" : "Cancel"}
          </Button>
          {!submitted && preview && (
            <Button
              style={{ cursor: "pointer" }}
              disabled={submit.isPending}
              onClick={() => submit.mutate()}
              data-testid="tier-upgrade-submit-button"
            >
              {submit.isPending ? "Processing…" : `Upgrade to ${preview.toTier}`}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
