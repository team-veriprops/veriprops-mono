"use client";

import { Loader2, ShieldCheck } from "lucide-react";
import { Button } from "@3rdparty/ui/button";
import { Badge } from "@3rdparty/ui/badge";
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
        <h1 className="text-2xl font-bold" style={{ color: "var(--brand-navy)" }}>Data &amp; privacy</h1>
        <p className="text-sm mt-1" style={{ color: "var(--brand-on-surface-variant)" }}>
          Manage your personal data. Under the Nigeria Data Protection Act you can request erasure of your data;
          audit and consent records are retained but your identity is pseudonymised.
        </p>
      </header>

      <div
        className="rounded-xl p-5"
        style={{ backgroundColor: "var(--brand-surface-card)", boxShadow: "0 1px 3px rgba(0,13,34,0.06)" }}
      >
        <div className="flex items-start gap-3">
          <span
            className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0"
            style={{ backgroundColor: "var(--brand-viridian-xlight)", color: "var(--brand-viridian)" }}
          >
            <ShieldCheck className="w-5 h-5" />
          </span>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold" style={{ color: "var(--brand-navy)" }}>Data erasure</p>

            {isLoading ? (
              <div className="flex items-center gap-2 py-4 text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>
                <Loader2 className="w-4 h-4 animate-spin" /> Loading…
              </div>
            ) : open ? (
              <div className="mt-2">
                <p className="text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>
                  Your erasure request is <Badge variant={STATUS_VARIANT[open.status]}>{open.status}</Badge>.
                  {open.slaDueAt ? ` We aim to review it by ${new Date(open.slaDueAt).toLocaleDateString()}.` : ""}
                </p>
              </div>
            ) : (
              <div className="mt-2">
                <p className="text-sm mb-3" style={{ color: "var(--brand-on-surface-variant)" }}>
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
          <h2 className="text-sm font-semibold mb-2" style={{ color: "var(--brand-navy)" }}>Request history</h2>
          <ul className="space-y-2">
            {requests.map((r) => (
              <li
                key={r.id}
                className="flex items-center justify-between rounded-lg px-4 py-3"
                style={{ backgroundColor: "var(--brand-surface-card)" }}
              >
                <span className="text-xs" style={{ color: "var(--brand-on-surface-variant)" }}>
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
