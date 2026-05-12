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
import { payoutAdminService } from "@components/agents/payouts/libs/payout-service";
import { getErrorMessage } from "@lib/utils";

const adminPayoutQKey = ["admin", "payouts"];

interface Props {
  payoutId: string;
  currentAmount: number;
  open: boolean;
  onClose: () => void;
}

export default function AdjustPayoutModal({ payoutId, currentAmount, open, onClose }: Props) {
  const qc = useQueryClient();
  const [newAmount, setNewAmount] = useState(String(currentAmount));
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const adjust = useMutation({
    mutationFn: () =>
      payoutAdminService.adjust(payoutId, parseFloat(newAmount), reason),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: adminPayoutQKey });
      setError(null);
      onClose();
    },
    onError: (e: any) => setError(getErrorMessage(e)),
  });

  const handleClose = () => {
    setNewAmount(String(currentAmount));
    setReason("");
    setError(null);
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent data-testid="adjust-payout-modal">
        <DialogHeader>
          <DialogTitle>Adjust Payout Amount</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Original Amount
            </label>
            <p className="text-sm text-gray-900 font-semibold">₦{currentAmount.toLocaleString()}</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              New Amount (₦) <span className="text-red-500">*</span>
            </label>
            <input
              type="number"
              min="0"
              step="0.01"
              value={newAmount}
              onChange={(e) => setNewAmount(e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              data-testid="adjust-payout-amount"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Reason <span className="text-red-500">*</span>
            </label>
            <textarea
              rows={3}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Explain the reason for this adjustment…"
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500"
              data-testid="adjust-payout-reason"
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
            disabled={adjust.isPending || !newAmount || !reason.trim()}
            onClick={() => adjust.mutate()}
            data-testid="adjust-payout-submit-button"
          >
            {adjust.isPending ? "Saving…" : "Save Adjustment"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
