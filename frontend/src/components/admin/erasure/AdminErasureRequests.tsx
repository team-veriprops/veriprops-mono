"use client";

import { CheckCircle2, XCircle, Trash2, Clock } from "lucide-react";
import { DEFAULT_PAGE_SIZE } from "@lib/config/app";
import { Action, Column, DataTable, TableFilterUpdate } from "@components/ui/table/DataTable";
import { PageShell } from "@components/ui/PageShell";
import { StatusPill } from "@components/ui/StatusPill";
import { AttentionChip } from "@components/ui/AttentionChip";
import { useSyncedQueryState } from "@hooks/useSyncedQueryState";
import { humanizeEnumLabel } from "@lib/utils";
import { Page } from "@/types/models";
import { DataErasureRequest, ErasureRequestStatus } from "@/types/erasure";
import {
  useAdminErasureRequestsQuery,
  useApproveErasureMutation,
  useExecuteErasureMutation,
  useRejectErasureMutation,
} from "@components/shared/erasure/libs/useErasureQueries";

const PAGE_SIZE = DEFAULT_PAGE_SIZE;

// A right-to-erasure request is still actionable while pending or approved; those are the
// rows whose review SLA matters.
const ACTIONABLE = new Set<ErasureRequestStatus>([
  ErasureRequestStatus.PENDING,
  ErasureRequestStatus.APPROVED,
]);

const columns: Column<DataErasureRequest & Record<string, unknown>>[] = [
  {
    key: "subjectUserId",
    label: "Subject",
    render: (_v, item) => <span className="font-mono text-xs">{item.subjectUserId}</span>,
  },
  {
    key: "status",
    label: "Status",
    render: (_v, item) => <StatusPill status={item.status} />,
  },
  { key: "reason", label: "Reason", render: (_v, item) => <span>{item.reason ?? "—"}</span> },
  {
    key: "slaDueAt",
    label: "Review by",
    render: (_v, item) => {
      if (!item.slaDueAt) return <span>—</span>;
      const overdue = ACTIONABLE.has(item.status) && new Date(item.slaDueAt).getTime() < Date.now();
      return overdue ? (
        <AttentionChip icon={Clock} tone="danger">
          Overdue {new Date(item.slaDueAt).toLocaleDateString()}
        </AttentionChip>
      ) : (
        <span>{new Date(item.slaDueAt).toLocaleDateString()}</span>
      );
    },
  },
  {
    key: "dateCreated",
    label: "Requested",
    render: (_v, item) => <span>{new Date(item.dateCreated).toLocaleDateString()}</span>,
  },
];

interface ErasureTableState extends Record<string, unknown> {
  page: number;
  status: string;
}

export default function AdminErasureRequests() {
  const [tableState, updateTableState] = useSyncedQueryState<ErasureTableState>({ page: 0, status: "" });
  const page = tableState.page ?? 0;
  const status = tableState.status ?? "";

  const { data, isLoading, isError, error } = useAdminErasureRequestsQuery(page, status || undefined);
  const approve = useApproveErasureMutation();
  const reject = useRejectErasureMutation();
  const execute = useExecuteErasureMutation();

  const dataPage: Page<DataErasureRequest & Record<string, unknown>> = (data as
    | Page<DataErasureRequest & Record<string, unknown>>
    | null) ?? {
    status: "success",
    code: "200",
    items: [],
    meta: { page, pageSize: PAGE_SIZE, count: 0, total: 0, totalPages: 0 },
  };

  const actions: Action<DataErasureRequest & Record<string, unknown>>[] = [
    {
      label: "Approve",
      icon: CheckCircle2,
      shown: (item) => item.status === ErasureRequestStatus.PENDING,
      onClick: (item) => approve.mutate(item.id),
    },
    {
      label: "Reject",
      icon: XCircle,
      variant: "destructive",
      shown: (item) => item.status === ErasureRequestStatus.PENDING,
      onClick: (item) => {
        const note = window.prompt("Reason for rejecting this erasure request (shown to the requester):") ?? undefined;
        reject.mutate({ id: item.id, note });
      },
    },
    {
      label: "Execute erasure",
      icon: Trash2,
      variant: "destructive",
      shown: (item) => item.status === ErasureRequestStatus.APPROVED,
      onClick: (item) => {
        if (
          window.confirm(
            "This permanently pseudonymises the subject's personal data (§4.11). It cannot be undone. Proceed?",
          )
        ) {
          execute.mutate(item.id);
        }
      },
    },
  ];

  const updateFilters = (u: TableFilterUpdate) => updateTableState(u as Partial<ErasureTableState>);

  return (
    <PageShell
      title="Data Erasure Requests"
      description="NDPA right-to-erasure queue (§18.1). Approving then executing pseudonymises the subject's PII irreversibly (§4.11)."
      width="wide"
      data-testid="admin-erasure-requests"
    >
      <DataTable<DataErasureRequest & Record<string, unknown>>
        dataPage={dataPage}
        columns={columns}
        actions={actions}
        currentPage={page}
        updateFilters={updateFilters}
        filters={[
          {
            key: "status",
            label: "Status",
            value: status,
            options: Object.values(ErasureRequestStatus).map((s) => ({ label: humanizeEnumLabel(s), value: s })),
          },
        ]}
        isLoading={isLoading}
        isError={isError}
        error={error as Error | null}
      />
    </PageShell>
  );
}
