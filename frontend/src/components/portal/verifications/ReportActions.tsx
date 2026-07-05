"use client";

import { useState } from "react";
import { toast } from "sonner";
import { RefreshCw, ArrowUpCircle, ShieldAlert } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@3rdparty/ui/dialog";
import { Button } from "@3rdparty/ui/button";
import { Textarea } from "@3rdparty/ui/textarea";
import { Label } from "@3rdparty/ui/label";
import {
  useOpenDisputeMutation,
  useRequestRecheckMutation,
  useRequestUpgradeMutation,
} from "@components/portal/libs/useRevisionQueries";
import { DisputeType } from "@/types/revision";
import { VerificationTier } from "@/types/verification";

const MIN_DISPUTE_CHARS = 100; // §14.3

const HIGHER_TIERS: Record<VerificationTier, VerificationTier[]> = {
  [VerificationTier.BASIC]: [VerificationTier.STANDARD, VerificationTier.PREMIUM],
  [VerificationTier.STANDARD]: [VerificationTier.PREMIUM],
  [VerificationTier.PREMIUM]: [],
};

/**
 * Customer post-report actions (§14): request a re-check, upgrade the tier, or file a dispute.
 * Each opens a focused dialog; the backend prices, gates the window, and drives the transitions.
 */
export function ReportActions({
  verificationId,
  tier,
}: {
  verificationId: string;
  tier?: VerificationTier;
}) {
  const [open, setOpen] = useState<"recheck" | "upgrade" | "dispute" | null>(null);
  const upgradeTargets = tier ? HIGHER_TIERS[tier] : [];

  return (
    <div className="flex flex-wrap gap-2">
      <Button size="sm" variant="outline" onClick={() => setOpen("recheck")} data-testid="action-recheck">
        <RefreshCw className="size-4" /> Request Re-check
      </Button>
      {upgradeTargets.length > 0 && (
        <Button size="sm" variant="outline" onClick={() => setOpen("upgrade")} data-testid="action-upgrade">
          <ArrowUpCircle className="size-4" /> Upgrade Tier
        </Button>
      )}
      <Button size="sm" variant="outline" onClick={() => setOpen("dispute")} data-testid="action-dispute">
        <ShieldAlert className="size-4" /> File a Dispute
      </Button>

      <RecheckDialog
        verificationId={verificationId}
        open={open === "recheck"}
        onClose={() => setOpen(null)}
      />
      <UpgradeDialog
        verificationId={verificationId}
        targets={upgradeTargets}
        open={open === "upgrade"}
        onClose={() => setOpen(null)}
      />
      <DisputeDialog
        verificationId={verificationId}
        open={open === "dispute"}
        onClose={() => setOpen(null)}
      />
    </div>
  );
}

function RecheckDialog({
  verificationId,
  open,
  onClose,
}: {
  verificationId: string;
  open: boolean;
  onClose: () => void;
}) {
  const [reason, setReason] = useState("");
  const request = useRequestRecheckMutation(verificationId);
  const submit = () => {
    if (reason.trim().length < 10) {
      toast.error("Please describe why you'd like a re-check.");
      return;
    }
    request.mutate(
      { reason: reason.trim() },
      {
        onSuccess: () => {
          toast.success("Re-check requested — our team will review it shortly.");
          setReason("");
          onClose();
        },
        onError: () => toast.error("Could not submit the re-check request."),
      },
    );
  };
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent data-testid="recheck-dialog">
        <DialogHeader>
          <DialogTitle>Request a re-check</DialogTitle>
          <DialogDescription>
            Tell us what you&apos;d like re-verified. An admin reviews the request and, once
            approved, you&apos;ll pay the re-check fee before the new cycle begins.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <Label htmlFor="recheck-reason">Reason</Label>
          <Textarea
            id="recheck-reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={4}
            placeholder="e.g. The survey plan doesn't match the plot I visited."
            data-testid="recheck-reason"
          />
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={submit} disabled={request.isPending} data-testid="recheck-submit">
            {request.isPending ? "Submitting…" : "Submit request"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function UpgradeDialog({
  verificationId,
  targets,
  open,
  onClose,
}: {
  verificationId: string;
  targets: VerificationTier[];
  open: boolean;
  onClose: () => void;
}) {
  const [toTier, setToTier] = useState<VerificationTier | "">("");
  const request = useRequestUpgradeMutation(verificationId);
  const submit = () => {
    if (!toTier) {
      toast.error("Select a tier to upgrade to.");
      return;
    }
    request.mutate(
      { toTier },
      {
        onSuccess: (res) => {
          const url = res.data?.checkoutUrl;
          toast.success("Upgrade created — complete payment to apply it.");
          onClose();
          if (url) window.location.assign(url);
        },
        onError: () => toast.error("Could not create the upgrade."),
      },
    );
  };
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent data-testid="upgrade-dialog">
        <DialogHeader>
          <DialogTitle>Upgrade your verification</DialogTitle>
          <DialogDescription>
            You only pay the price difference. The added checks are carried out and a new report
            version is issued; your existing findings are preserved.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <Label htmlFor="upgrade-tier">Upgrade to</Label>
          <select
            id="upgrade-tier"
            className="w-full rounded-md border bg-background p-2 text-sm"
            value={toTier}
            onChange={(e) => setToTier(e.target.value as VerificationTier)}
            data-testid="upgrade-tier"
          >
            <option value="">Select a tier…</option>
            {targets.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={submit} disabled={request.isPending} data-testid="upgrade-submit">
            {request.isPending ? "Creating…" : "Continue to payment"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function DisputeDialog({
  verificationId,
  open,
  onClose,
}: {
  verificationId: string;
  open: boolean;
  onClose: () => void;
}) {
  const [type, setType] = useState<DisputeType>(DisputeType.INACCURATE_FINDING);
  const [description, setDescription] = useState("");
  const openDispute = useOpenDisputeMutation(verificationId);
  const tooShort = description.trim().length < MIN_DISPUTE_CHARS;
  const submit = () => {
    if (tooShort) {
      toast.error(`Please describe the issue in at least ${MIN_DISPUTE_CHARS} characters.`);
      return;
    }
    openDispute.mutate(
      { disputeType: type, description: description.trim() },
      {
        onSuccess: () => {
          toast.success("Dispute filed — an admin will review it within 5 business days.");
          setDescription("");
          onClose();
        },
        onError: () => toast.error("Could not file the dispute. Check the dispute window."),
      },
    );
  };
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent data-testid="dispute-dialog">
        <DialogHeader>
          <DialogTitle>File a dispute</DialogTitle>
          <DialogDescription>
            Disputes are reviewed by an admin. If your task involved a specific agent, they may be
            asked to respond — always through us, never directly.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-2">
            <Label htmlFor="dispute-type">Type</Label>
            <select
              id="dispute-type"
              className="w-full rounded-md border bg-background p-2 text-sm"
              value={type}
              onChange={(e) => setType(e.target.value as DisputeType)}
              data-testid="dispute-type"
            >
              {Object.values(DisputeType).map((t) => (
                <option key={t} value={t}>{t.replace(/_/g, " ")}</option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <Label htmlFor="dispute-desc">What went wrong?</Label>
            <Textarea
              id="dispute-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={5}
              data-testid="dispute-desc"
            />
            <p className={`text-xs ${tooShort ? "text-amber-600" : "text-muted-foreground"}`}>
              {description.trim().length}/{MIN_DISPUTE_CHARS} characters minimum
            </p>
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={submit} disabled={openDispute.isPending || tooShort} data-testid="dispute-submit">
            {openDispute.isPending ? "Filing…" : "File dispute"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
