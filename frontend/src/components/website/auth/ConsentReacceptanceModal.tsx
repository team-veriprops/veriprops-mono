"use client";

import { useState } from "react";
import Link from "next/link";
import { ShieldCheck } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@3rdparty/ui/dialog";
import { Button } from "@3rdparty/ui/button";
import { Checkbox } from "@3rdparty/ui/checkbox";
import {
  useAcceptConsentsMutation,
  useMissingConsentsQuery,
} from "./libs/useAuthQueries";
import { useAuthStore } from "@components/website/auth/libs/useAuthStore";
import { getErrorMessage } from "@lib/utils";

/**
 * Mounted in the authenticated portal layout. If the backend reports any
 * required consent the user has not yet accepted (or has only accepted an
 * older version of), it shows a non-dismissible modal.
 *
 * PRD §3.2: version bumps force re-acceptance — modal cannot be dismissed,
 * accept or decline.
 */
export default function ConsentReacceptanceModal() {
  const session = useAuthStore((s) => s.session);
  const enabled = !!session;
  const { data: documents = [], refetch } = useMissingConsentsQuery(enabled);
  const accept = useAcceptConsentsMutation();
  const [accepted, setAccepted] = useState<Record<string, boolean>>({});
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const open = enabled && documents.length > 0;
  const allAccepted = documents.every((d) => accepted[d.type]);

  const handleAccept = async () => {
    setErrorMessage(null);
    try {
      const now = new Date().toISOString();
      await accept.mutateAsync(
        documents.map((d) => ({
          documentType: d.type,
          consentVersion: d.consentVersion,
          acceptedAt: now,
        })),
      );
      await refetch();
    } catch (err) {
      setErrorMessage(
        getErrorMessage(err as Error, "Could not record your acceptance. Please try again."),
      );
    }
  };

  return (
    <Dialog open={open}>
      <DialogContent showCloseButton={false} className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-xl font-semibold">
            <ShieldCheck className="w-5 h-5" style={{ color: "var(--brand-viridian)" }} />
            Updated terms — please review
          </DialogTitle>
        </DialogHeader>

        <p className="text-sm leading-relaxed mt-2" style={{ color: "var(--brand-on-surface-variant)" }}>
          We&apos;ve published new versions of the documents below. Please review and accept to continue
          using Veriprops. Your previous acceptance is on record and remains audit-logged.
        </p>

        <div className="space-y-3 mt-4">
          {documents.map((doc) => {
            const id = `consent-${doc.type}`;
            return (
              <label
                key={doc.type}
                htmlFor={id}
                className="flex items-start gap-3 p-3 rounded-lg cursor-pointer select-none transition-colors hover:bg-[var(--brand-surface-low)]"
                style={{ backgroundColor: "var(--brand-surface-low)" }}
              >
                <Checkbox
                  id={id}
                  checked={!!accepted[doc.type]}
                  onCheckedChange={(v) =>
                    setAccepted((prev) => ({ ...prev, [doc.type]: v === true }))
                  }
                  className="mt-0.5"
                />
                <span className="text-sm leading-relaxed" style={{ color: "var(--brand-on-surface)" }}>
                  I have read and accept the{" "}
                  <Link
                    href={doc.href}
                    target="_blank"
                    rel="noopener"
                    className="font-semibold underline-offset-2 hover:underline"
                    style={{ color: "var(--brand-viridian)" }}
                  >
                    {doc.title}
                  </Link>{" "}
                  <span className="font-mono text-[11px]" style={{ color: "var(--brand-on-surface-variant)" }}>
                    v{doc.consentVersion}
                  </span>
                </span>
              </label>
            );
          })}
        </div>

        {errorMessage && (
          <p className="text-sm mt-3" style={{ color: "var(--danger)" }}>
            {errorMessage}
          </p>
        )}

        <div className="mt-6">
          <Button
            type="button"
            className="w-full"
            size="lg"
            disabled={!allAccepted || accept.isPending}
            onClick={handleAccept}
          >
            {accept.isPending ? "Saving…" : "I accept all updated terms"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
