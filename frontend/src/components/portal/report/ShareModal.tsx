"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Copy, Check, X } from "lucide-react";
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

type ShareMode = "PRIVATE" | "LINK_ONLY" | "PUBLIC" | "NAMED_RECIPIENT";

interface ShareLink {
  id: string;
  token: string;
  mode: ShareMode;
  expiresAt: string | null;
}

interface Props {
  verificationId: string;
  open: boolean;
  onClose: () => void;
}

export default function ShareModal({ verificationId, open, onClose }: Props) {
  const [mode, setMode] = useState<ShareMode>("LINK_ONLY");
  const [recipientEmail, setRecipientEmail] = useState("");
  const [link, setLink] = useState<ShareLink | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const createShare = useMutation({
    mutationFn: () =>
      httpClient.post(`/api/portal/verifications/${verificationId}/share`, {
        mode,
        recipientEmail: mode === "NAMED_RECIPIENT" ? recipientEmail : undefined,
        expiryDays: 30,
      }),
    onSuccess: (res: any) => {
      setLink(res.data);
      setError(null);
    },
    onError: (e: any) => setError(getErrorMessage(e)),
  });

  const revokeShare = useMutation({
    mutationFn: () =>
      httpClient.delete(`/api/portal/verifications/${verificationId}/share/${link!.id}`),
    onSuccess: () => {
      setLink(null);
      setError(null);
    },
    onError: (e: any) => setError(getErrorMessage(e)),
  });

  const shareUrl = link ? `${window.location.origin}/verify/${verificationId}?token=${link.token}` : "";

  const copyLink = async () => {
    await navigator.clipboard.writeText(shareUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleClose = () => {
    setLink(null);
    setMode("LINK_ONLY");
    setRecipientEmail("");
    setError(null);
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent data-testid="share-modal">
        <DialogHeader>
          <DialogTitle>Share Verification</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Sharing Mode</label>
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value as ShareMode)}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              style={{ cursor: "pointer" }}
              data-testid="share-mode-select"
            >
              <option value="PRIVATE">Private (no sharing)</option>
              <option value="LINK_ONLY">Link-only (anyone with link)</option>
              <option value="PUBLIC">Public (discoverable)</option>
              <option value="NAMED_RECIPIENT">Named recipient (specific email)</option>
            </select>
          </div>

          {mode === "NAMED_RECIPIENT" && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Recipient Email</label>
              <input
                type="email"
                value={recipientEmail}
                onChange={(e) => setRecipientEmail(e.target.value)}
                placeholder="recipient@example.com"
                className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                data-testid="share-recipient-email"
              />
              <p className="mt-1 text-xs text-gray-500">
                Recipient will need to acknowledge a disclaimer before viewing the report.
              </p>
            </div>
          )}

          {link && (
            <div className="rounded-md border border-indigo-200 bg-indigo-50 p-3 space-y-2">
              <p className="text-xs font-medium text-indigo-800">Share link created</p>
              <div className="flex items-center gap-2">
                <input
                  readOnly
                  value={shareUrl}
                  className="flex-1 rounded border border-indigo-200 bg-white px-2 py-1 text-xs font-mono text-gray-700"
                  data-testid="share-link-url"
                />
                <button
                  type="button"
                  onClick={copyLink}
                  style={{ cursor: "pointer" }}
                  className="p-1.5 rounded border border-indigo-300 text-indigo-700 hover:bg-indigo-100"
                  data-testid="share-copy-button"
                >
                  {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                </button>
              </div>
              {link.expiresAt && (
                <p className="text-xs text-indigo-600">
                  Expires: {new Date(link.expiresAt).toLocaleDateString()}
                </p>
              )}
              <button
                type="button"
                onClick={() => revokeShare.mutate()}
                disabled={revokeShare.isPending}
                style={{ cursor: "pointer" }}
                className="flex items-center gap-1 text-xs text-red-600 hover:underline"
                data-testid="share-revoke-button"
              >
                <X className="h-3 w-3" />
                {revokeShare.isPending ? "Revoking…" : "Revoke link"}
              </button>
            </div>
          )}

          {error && <p className="text-sm text-red-600">{error}</p>}
        </div>
        <DialogFooter>
          <Button variant="outline" style={{ cursor: "pointer" }} onClick={handleClose}>
            Close
          </Button>
          {!link && (
            <Button
              style={{ cursor: "pointer" }}
              disabled={createShare.isPending || (mode === "NAMED_RECIPIENT" && !recipientEmail)}
              onClick={() => createShare.mutate()}
              data-testid="share-create-button"
            >
              {createShare.isPending ? "Creating…" : "Create Link"}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
