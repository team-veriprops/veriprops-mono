"use client";

import { Loader2, ShieldCheck } from "lucide-react";
import { Button } from "@3rdparty/ui/button";
import { Badge } from "@3rdparty/ui/badge";
import { cn } from "@lib/utils";
import { DataErasureRequest, ErasureRequestStatus } from "@/types/erasure";
import {
  useMyErasureRequestsQuery,
  useRequestErasureMutation,
} from "@components/shared/erasure/libs/useErasureQueries";

const OPEN_STATES = new Set<ErasureRequestStatus>([
  ErasureRequestStatus.PENDING,
  ErasureRequestStatus.APPROVED,
]);

const STATUS_VARIANT: Record<ErasureRequestStatus, "default" | "secondary" | "destructive" | "outline"> = {
  [ErasureRequestStatus.PENDING]: "default",
  [ErasureRequestStatus.APPROVED]: "secondary",
  [ErasureRequestStatus.EXECUTED]: "outline",
  [ErasureRequestStatus.REJECTED]: "destructive",
};

/** Account → Data & privacy (§N.5, §19.1). Self-service NDPA data-erasure request + status. */
export default function DataPrivacy() {
  const { data, isLoading } = useMyErasureRequestsQuery();
  const request = useRequestErasureMutation();

  const requests: DataErasureRequest[] = data ?? [];
  const open = requests.find((r) => OPEN_STATES.has(r.status));

  const submit = () => {
    if (
      window.confirm(
        "Request erasure of your personal data under the NDPA? An admin will review it. " +
          "Once carried out, your identifying details are permanently removed and you will no longer be able to sign in.",
      )
    ) {
      request.mutate(undefined);
    }
  };

  return (
    <div className="max-w-3xl mx-auto px-4 md:px-8 py-8" data-testid="data-privacy">
      <header className="mb-6">
        <h1 className={cn("text-2xl font-bold text-brand-navy")}>Data &amp; privacy</h1>
        <p className={cn("text-sm mt-1 text-brand-on-surface-variant")}>
          Manage your personal data. Under the Nigeria Data Protection Act you can request erasure of your data;
          audit and consent records are retained but your identity is pseudonymised.
        </p>
      </header>

      <div className={cn("rounded-xl p-5 bg-brand-surface-card shadow-card")}>
        <div className="flex items-start gap-3">
          <span
            className={cn("w-9 h-9 rounded-lg flex items-center justify-center shrink-0 bg-brand-viridian-xlight text-brand-viridian")}
          >
            <ShieldCheck className="w-5 h-5" />
          </span>
          <div className="flex-1 min-w-0">
            <p className={cn("text-sm font-semibold text-brand-navy")}>Data erasure</p>

            {isLoading ? (
              <div className={cn("flex items-center gap-2 py-4 text-sm text-brand-on-surface-variant")}>
                <Loader2 className="w-4 h-4 animate-spin" /> Loading…
              </div>
            ) : open ? (
              <div className="mt-2">
                <p className={cn("text-sm text-brand-on-surface-variant")}>
                  Your erasure request is <Badge variant={STATUS_VARIANT[open.status]}>{open.status}</Badge>.
                  {open.slaDueAt ? ` We aim to review it by ${new Date(open.slaDueAt).toLocaleDateString()}.` : ""}
                </p>
              </div>
            ) : (
              <div className="mt-2">
                <p className={cn("text-sm mb-3 text-brand-on-surface-variant")}>
                  You can request that we erase your personal data. This action is reviewed by our team.
                </p>
                <Button variant="destructive" onClick={submit} disabled={request.isPending} data-testid="request-erasure">
                  {request.isPending ? "Submitting…" : "Request data erasure"}
                </Button>
              </div>
            )}
          </div>
        </div>
      </div>

      {requests.length > 0 && (
        <div className="mt-6">
          <h2 className={cn("text-sm font-semibold mb-2 text-brand-navy")}>Request history</h2>
          <ul className="space-y-2">
            {requests.map((r) => (
              <li
                key={r.id}
                className={cn("flex items-center justify-between rounded-lg px-4 py-3 bg-brand-surface-card")}
              >
                <span className={cn("text-xs text-brand-on-surface-variant")}>
                  {new Date(r.dateCreated).toLocaleString()}
                  {r.decisionNote ? ` · ${r.decisionNote}` : ""}
                </span>
                <Badge variant={STATUS_VARIANT[r.status]}>{r.status}</Badge>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
