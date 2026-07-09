"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Globe, Link2, Mail, Trash2 } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@3rdparty/ui/dialog";
import { Button } from "@3rdparty/ui/button";
import { Input } from "@3rdparty/ui/input";
import { Label } from "@3rdparty/ui/label";
import { CopyText } from "@components/ui/CopyText";
import {
  useCreateShareMutation,
  useRevokeShareMutation,
  useSetPublicVisibilityMutation,
  useSharesQuery,
} from "@components/portal/libs/useShareQueries";
import { ShareType, Share } from "@/types/share";

/**
 * Report sharing controls (§13.2): toggle public VID lookup, create a summary link, invite
 * a named recipient to the full report, and revoke any active share. Backend owns tokens,
 * expiry, and the summary allow-list.
 */
export function ReportShareModal({
  verificationId,
  vid,
  open,
  onOpenChange,
}: {
  verificationId: string;
  vid: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { data: shares } = useSharesQuery(open ? verificationId : null);
  const createShare = useCreateShareMutation(verificationId);
  const revokeShare = useRevokeShareMutation(verificationId);
  const setPublic = useSetPublicVisibilityMutation(verificationId);
  const [email, setEmail] = useState("");

  const active = (shares ?? []).filter((s) => s.active);

  const createLink = () =>
    createShare.mutate(
      { shareType: ShareType.LINK_SUMMARY },
      { onSuccess: () => toast.success("Share link created") },
    );

  const inviteNamed = () => {
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      toast.error("Enter a valid email address");
      return;
    }
    createShare.mutate(
      { shareType: ShareType.NAMED_FULL, recipientEmail: email.trim() },
      {
        onSuccess: () => {
          toast.success(`Full report shared with ${email.trim()}`);
          setEmail("");
        },
      },
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg" data-testid="report-share-modal">
        <DialogHeader>
          <DialogTitle>Share this report</DialogTitle>
          <DialogDescription>
            Public and link shares show a summary only. Named recipients see the full report after
            acknowledging a disclaimer. Every share is time-limited and revocable.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5">
          {/* Public VID lookup */}
          <div className="flex items-center justify-between rounded-lg border p-3">
            <div className="flex items-start gap-2">
              <Globe className="mt-0.5 size-4 text-muted-foreground" />
              <div>
                <p className="text-sm font-medium">Public lookup</p>
                <p className="text-xs text-muted-foreground">
                  Anyone with the ID {vid} can see the summary at /verify/{vid}.
                </p>
              </div>
            </div>
            <Button
              size="sm"
              variant="outline"
              disabled={setPublic.isPending}
              onClick={() => setPublic.mutate(true)}
              data-testid="share-enable-public"
            >
              Enable
            </Button>
          </div>

          {/* Link-only summary share */}
          <div className="flex items-center justify-between rounded-lg border p-3">
            <div className="flex items-start gap-2">
              <Link2 className="mt-0.5 size-4 text-muted-foreground" />
              <div>
                <p className="text-sm font-medium">Summary link</p>
                <p className="text-xs text-muted-foreground">Anyone with the link sees the summary.</p>
              </div>
            </div>
            <Button size="sm" disabled={createShare.isPending} onClick={createLink} data-testid="share-create-link">
              Create link
            </Button>
          </div>

          {/* Named recipient full report */}
          <div className="rounded-lg border p-3">
            <div className="flex items-start gap-2">
              <Mail className="mt-0.5 size-4 text-muted-foreground" />
              <div className="flex-1">
                <Label htmlFor="share-email" className="text-sm font-medium">
                  Send the full report to someone
                </Label>
                <div className="mt-2 flex gap-2">
                  <Input
                    id="share-email"
                    type="email"
                    placeholder="lawyer@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    data-testid="share-named-email"
                  />
                  <Button disabled={createShare.isPending} onClick={inviteNamed} data-testid="share-named-send">
                    Send
                  </Button>
                </div>
              </div>
            </div>
          </div>

          {/* Active shares */}
          {active.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase text-muted-foreground">Active shares</p>
              {active.map((s) => (
                <ShareRow
                  key={s.id}
                  share={s}
                  onRevoke={() =>
                    revokeShare.mutate(s.id, { onSuccess: () => toast.success("Share revoked") })
                  }
                  revoking={revokeShare.isPending}
                />
              ))}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function ShareRow({
  share,
  onRevoke,
  revoking,
}: {
  share: Share;
  onRevoke: () => void;
  revoking: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-2 rounded-md border p-2 text-sm">
      <div className="min-w-0">
        <p className="font-medium">
          {share.shareType === ShareType.NAMED_FULL ? `Full report → ${share.recipientEmail}` : "Summary link"}
        </p>
        <div className="mt-1">
          <CopyText text={share.shareUrl} />
        </div>
      </div>
      <Button
        size="icon"
        variant="ghost"
        disabled={revoking}
        onClick={onRevoke}
        aria-label="Revoke share"
        data-testid="share-revoke"
      >
        <Trash2 className="size-4 text-destructive" />
      </Button>
    </div>
  );
}
