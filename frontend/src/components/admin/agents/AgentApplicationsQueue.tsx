"use client";

import { useState } from "react";
import { Button } from "@3rdparty/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@3rdparty/ui/dialog";
import {
  useAgentApplications,
  useApproveApplicationMutation,
  useRejectApplicationMutation,
} from "../libs/useAdminQueries";
import type { AdminAgentApplication } from "../libs/admin-service";
import { CheckCircle2, XCircle } from "lucide-react";
import { getErrorMessage } from "@lib/utils";

type StatusFilter = "PENDING" | "APPROVED" | "REJECTED";

export default function AgentApplicationsQueue() {
  const [filter, setFilter] = useState<StatusFilter>("PENDING");
  const { data, isLoading } = useAgentApplications(filter);
  const approve = useApproveApplicationMutation();
  const reject = useRejectApplicationMutation();
  const [selected, setSelected] = useState<AdminAgentApplication | null>(null);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const closeDrawer = () => {
    setSelected(null);
    setReason("");
    setError(null);
  };

  const handleApprove = async () => {
    if (!selected) return;
    try {
      await approve.mutateAsync(selected.id);
      closeDrawer();
    } catch (e) {
      setError(getErrorMessage(e as Error));
    }
  };

  const handleReject = async () => {
    if (!selected) return;
    if (reason.trim().length < 30) {
      setError("Rejection reason must be at least 30 characters.");
      return;
    }
    try {
      await reject.mutateAsync({ id: selected.id, reason });
      closeDrawer();
    } catch (e) {
      setError(getErrorMessage(e as Error));
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1
          className="text-3xl font-semibold tracking-tight"
          style={{ color: "var(--brand-navy)", fontFamily: "var(--font-display, Manrope)" }}
        >
          Agent applications
        </h1>
        <p className="text-sm mt-1" style={{ color: "var(--brand-on-surface-variant)" }}>
          Approve or reject agent applications. Pending applications block the agent from receiving jobs.
        </p>
      </div>

      <div className="inline-flex rounded-lg p-1 gap-1" style={{ backgroundColor: "var(--brand-surface-low)" }}>
        {(["PENDING", "APPROVED", "REJECTED"] as StatusFilter[]).map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => setFilter(s)}
            className="text-xs font-medium px-3 py-1.5 rounded-md"
            style={{
              backgroundColor: filter === s ? "white" : "transparent",
              color: filter === s ? "var(--brand-navy)" : "var(--brand-on-surface-variant)",
              boxShadow: filter === s ? "0px 4px 12px rgba(0,13,34,0.06)" : undefined,
            }}
          >
            {s}
          </button>
        ))}
      </div>

      <div
        className="rounded-2xl overflow-hidden"
        style={{
          backgroundColor: "var(--brand-surface-card)",
          boxShadow: "0px 24px 48px rgba(0,13,34,0.06)",
        }}
      >
        <table className="w-full text-sm">
          <thead>
            <tr style={{ backgroundColor: "var(--brand-surface-low)" }}>
              <Th>Applicant</Th>
              <Th>Roles</Th>
              <Th>Coverage</Th>
              <Th>Submitted</Th>
              <Th className="text-right">Action</Th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={5} className="text-center py-8" style={{ color: "var(--brand-on-surface-variant)" }}>
                  Loading…
                </td>
              </tr>
            ) : !data?.items?.length ? (
              <tr>
                <td colSpan={5} className="text-center py-8" style={{ color: "var(--brand-on-surface-variant)" }}>
                  No applications.
                </td>
              </tr>
            ) : (
              data.items.map((app) => (
                <tr key={app.id} className="border-t" style={{ borderColor: "var(--brand-surface-low)" }}>
                  <Td>
                    <div className="font-medium" style={{ color: "var(--brand-navy)" }}>
                      {app.userFirstName} {app.userLastName}
                    </div>
                    <div className="text-xs" style={{ color: "var(--brand-on-surface-variant)" }}>
                      {app.userEmail}
                    </div>
                  </Td>
                  <Td>{app.types.join(" · ")}</Td>
                  <Td>
                    <span style={{ color: "var(--brand-on-surface-variant)" }}>
                      {app.coverageStates.length} states · {app.coverageLgas.length} LGAs
                    </span>
                  </Td>
                  <Td>
                    {app.submittedAt
                      ? new Date(app.submittedAt).toLocaleDateString()
                      : "—"}
                  </Td>
                  <Td className="text-right">
                    <Button type="button" variant="outline" size="sm" onClick={() => setSelected(app)}>
                      Review
                    </Button>
                  </Td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <Dialog open={!!selected} onOpenChange={(v) => (!v ? closeDrawer() : null)}>
        <DialogContent className="sm:max-w-2xl">
          {selected && (
            <>
              <DialogHeader>
                <DialogTitle>
                  {selected.userFirstName} {selected.userLastName}
                </DialogTitle>
                <DialogDescription>{selected.userEmail}</DialogDescription>
              </DialogHeader>

              <div className="space-y-4 text-sm">
                <Section label="Roles">{selected.types.join(" · ")}</Section>
                <Section label="KYC method">
                  {selected.kycMethod === "BVN"
                    ? `BVN ••${selected.bvnLast4 ?? "----"}`
                    : selected.kycMethod === "ID_DOC"
                    ? `${selected.idDocType} + selfie (match ${selected.selfieMatchScore}/100)`
                    : "—"}
                </Section>
                {selected.surveyorLicenceNo && (
                  <Section label="Surveyor licence">
                    {selected.surveyorLicenceNo}
                    {selected.surveyorLicenceUrl && (
                      <>
                        {" · "}
                        <a href={selected.surveyorLicenceUrl} target="_blank" rel="noopener" style={{ color: "var(--brand-viridian)" }}>
                          view
                        </a>
                      </>
                    )}
                  </Section>
                )}
                {selected.nbaLicenceNo && (
                  <Section label="NBA licence">
                    {selected.nbaLicenceNo}
                    {selected.nbaLicenceUrl && (
                      <>
                        {" · "}
                        <a href={selected.nbaLicenceUrl} target="_blank" rel="noopener" style={{ color: "var(--brand-viridian)" }}>
                          view
                        </a>
                      </>
                    )}
                  </Section>
                )}
                <Section label="Coverage states">
                  {selected.coverageStates.join(", ") || "—"}
                </Section>
                {selected.bio && <Section label="Bio">{selected.bio}</Section>}

                {filter === "PENDING" && (
                  <div className="space-y-2 pt-3 border-t" style={{ borderColor: "var(--brand-surface-low)" }}>
                    <label
                      className="text-xs font-medium block"
                      style={{ color: "var(--brand-on-surface-variant)" }}
                    >
                      Rejection reason (≥ 30 chars)
                    </label>
                    <textarea
                      rows={3}
                      className="w-full rounded-md p-3 text-sm"
                      style={{
                        backgroundColor: "var(--brand-surface-card)",
                        border: "1px solid var(--border)",
                        color: "var(--brand-navy)",
                      }}
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                    />
                  </div>
                )}

                {error && (
                  <div
                    className="text-sm rounded-md p-3"
                    style={{
                      color: "var(--destructive)",
                      backgroundColor: "rgba(186,26,26,0.06)",
                    }}
                  >
                    {error}
                  </div>
                )}
              </div>

              <DialogFooter>
                <Button type="button" variant="outline" onClick={closeDrawer}>
                  Close
                </Button>
                {filter === "PENDING" && (
                  <>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={handleReject}
                      disabled={reject.isPending}
                    >
                      <XCircle className="w-4 h-4 mr-2" />
                      Reject
                    </Button>
                    <Button
                      type="button"
                      onClick={handleApprove}
                      disabled={approve.isPending}
                    >
                      <CheckCircle2 className="w-4 h-4 mr-2" />
                      Approve
                    </Button>
                  </>
                )}
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

function Th({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <th
      className={`text-xs font-semibold uppercase tracking-wider px-4 py-3 text-left ${className ?? ""}`}
      style={{ color: "var(--brand-on-surface-variant)" }}
    >
      {children}
    </th>
  );
}
function Td({ children, className }: { children: React.ReactNode; className?: string }) {
  return <td className={`px-4 py-3 ${className ?? ""}`}>{children}</td>;
}
function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div
        className="text-[11px] font-semibold uppercase tracking-wider mb-1"
        style={{ color: "var(--brand-on-surface-variant)" }}
      >
        {label}
      </div>
      <div style={{ color: "var(--brand-navy)" }}>{children}</div>
    </div>
  );
}
