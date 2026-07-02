"use client";

import { useState } from "react";
import { Badge } from "@3rdparty/ui/badge";
import { Button } from "@3rdparty/ui/button";
import { Input } from "@3rdparty/ui/input";
import { toast } from "@components/3rdparty/ui/use-toast";
import { Column, DataTable } from "@components/ui/table/DataTable";
import DetailDrawer, { DetailDrawerWidth } from "@components/ui/DetailDrawer";
import { PageRequest } from "@/types/models";
import { AgentApplicationStatus, AgentApplicationSummary } from "@/types/agent";
import {
  useAgentApplicationQuery,
  useAgentApplicationsQuery,
  useApproveAgentMutation,
  useRejectAgentMutation,
} from "@components/agents/libs/useAgentQueries";

const STATUS_VARIANT: Record<AgentApplicationStatus, "default" | "secondary" | "destructive"> = {
  [AgentApplicationStatus.PENDING]: "secondary",
  [AgentApplicationStatus.APPROVED]: "default",
  [AgentApplicationStatus.REJECTED]: "destructive",
};

const columns: Column<AgentApplicationSummary & Record<string, unknown>>[] = [
  { key: "applicantName", label: "Applicant" },
  {
    key: "roles",
    label: "Roles",
    render: (_v, item) => item.roles.join(", "),
  },
  {
    key: "status",
    label: "Status",
    render: (_v, item) => <Badge variant={STATUS_VARIANT[item.status]}>{item.status}</Badge>,
  },
  {
    key: "submittedAt",
    label: "Submitted",
    render: (_v, item) => (item.submittedAt ? new Date(item.submittedAt).toLocaleDateString() : "—"),
  },
];

export default function AgentApplicationsAdmin() {
  const [page, setPage] = useState(0);
  const [status] = useState<string | undefined>(AgentApplicationStatus.PENDING);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState("");

  const pageSize = 10;
  const { data: pageData, isLoading, isError, error } = useAgentApplicationsQuery(status, page, pageSize);
  const { data: detail } = useAgentApplicationQuery(selectedId);
  const approve = useApproveAgentMutation();
  const reject = useRejectAgentMutation();

  const updateFilters = (updates: Partial<PageRequest>) => {
    if (updates.page !== undefined) setPage(updates.page);
  };

  const onApprove = async () => {
    if (!detail) return;
    await approve.mutateAsync({ id: detail.id });
    toast({ title: "Application approved" });
    setSelectedId(null);
  };

  const onReject = async () => {
    if (!detail || !rejectReason.trim()) return;
    await reject.mutateAsync({ id: detail.id, reason: rejectReason.trim() });
    toast({ title: "Application rejected" });
    setRejectReason("");
    setSelectedId(null);
  };

  const emptyPage = {
    status: "success",
    code: "200",
    items: [] as (AgentApplicationSummary & Record<string, unknown>)[],
    meta: { page: 0, pageSize, count: 0, total: 0, totalPages: 0 },
  };

  return (
    <div className="space-y-6" data-testid="admin-agent-applications">
      <h1 className="text-2xl font-bold text-foreground">Agent applications</h1>

      <DataTable<AgentApplicationSummary & Record<string, unknown>>
        dataPage={
          (pageData?.data as typeof emptyPage) ?? emptyPage
        }
        columns={columns}
        currentPage={page}
        updateFilters={updateFilters}
        isLoading={isLoading}
        isError={isError}
        error={error as Error | null}
        isRowClickable
        onRowClick={(row) => setSelectedId(row.id)}
        searchPlaceholder="Search applicants…"
      />

      <DetailDrawer
        open={!!selectedId}
        onOpenChange={(o) => !o && setSelectedId(null)}
        title={detail?.applicantName ?? "Application"}
        reference={detail?.applicantEmail ?? ""}
        drawerWidth={DetailDrawerWidth.LARGE}
      >
        {detail && (
          <div className="space-y-6 p-6" data-testid="admin-agent-detail">
            <section className="space-y-2 text-sm">
              <Row label="Status" value={detail.status} />
              <Row label="Applied roles" value={detail.roles.join(", ")} />
              <Row label="Approved roles" value={detail.approvedRoles.join(", ") || "—"} />
              {detail.bio && <Row label="Bio" value={detail.bio} />}
              {detail.yearsExperience != null && (
                <Row label="Experience" value={`${detail.yearsExperience} years`} />
              )}
            </section>

            <section>
              <h3 className="mb-2 font-medium">KYC</h3>
              {detail.kyc ? (
                <div className="rounded-lg border border-border p-3 text-sm">
                  <Row label="Method" value={detail.kyc.method} />
                  <Row label="Result" value={detail.kyc.status} />
                  {detail.kyc.score != null && <Row label="Score" value={String(detail.kyc.score)} />}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">No KYC record.</p>
              )}
            </section>

            {detail.credentials.length > 0 && (
              <section>
                <h3 className="mb-2 font-medium">Credentials</h3>
                <ul className="space-y-1 text-sm">
                  {detail.credentials.map((c) => (
                    <li key={c.role} className="rounded border border-border p-2">
                      {c.role} — {c.credentialType} ({c.status})
                      {c.expiryDate ? ` · expires ${c.expiryDate}` : ""}
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {detail.status === AgentApplicationStatus.PENDING && (
              <section className="space-y-3 border-t border-border pt-4">
                <Button
                  onClick={onApprove}
                  disabled={approve.isPending}
                  data-testid="admin-agent-approve"
                >
                  Approve all applied roles
                </Button>
                <div className="space-y-2">
                  <Input
                    placeholder="Reason for rejection"
                    value={rejectReason}
                    onChange={(e) => setRejectReason(e.target.value)}
                    data-testid="admin-agent-reject-reason"
                  />
                  <Button
                    variant="destructive"
                    onClick={onReject}
                    disabled={reject.isPending || !rejectReason.trim()}
                    data-testid="admin-agent-reject"
                  >
                    Reject
                  </Button>
                </div>
              </section>
            )}
          </div>
        )}
      </DetailDrawer>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4">
      <span className="text-muted-foreground">{label}</span>
      <span className="text-right font-medium">{value}</span>
    </div>
  );
}
