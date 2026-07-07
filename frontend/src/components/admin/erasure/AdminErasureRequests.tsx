"use client";

import { CheckCircle2, XCircle, Trash2 } from "lucide-react";
import { Badge } from "@3rdparty/ui/badge";
import { Action, Column, DataTable, TableFilterUpdate } from "@components/ui/table/DataTable";
import { useSyncedQueryState } from "@hooks/useSyncedQueryState";
import { Page } from "@/types/models";
import { DataErasureRequest, ErasureRequestStatus } from "@/types/erasure";
import {
  useAdminErasureRequestsQuery,
  useApproveErasureMutation,
  useExecuteErasureMutation,
  useRejectErasureMutation,
} from "@components/shared/erasure/libs/useErasureQueries";

const PAGE_SIZE = 10;

const STATUS_VARIANT: Record<ErasureRequestStatus, "default" | "secondary" | "destructive" | "outline"> = {
  [ErasureRequestStatus.PENDING]: "default",
  [ErasureRequestStatus.APPROVED]: "secondary",
  [ErasureRequestStatus.EXECUTED]: "outline",
  [ErasureRequestStatus.REJECTED]: "destructive",
};

const columns: Column<DataErasureRequest & Record<string, unknown>>[] = [
  {
    key: "subjectUserId",
    label: "Subject",
    render: (_v, item) => <span className="font-mono text-xs">{item.subjectUserId}</span>,
  },
  {
    key: "status",
    label: "Status",
    render: (_v, item) => <Badge variant={STATUS_VARIANT[item.status]}>{item.status}</Badge>,
  },
  { key: "reason", label: "Reason", render: (_v, item) => <span>{item.reason ?? "—"}</span> },
  {
    key: "slaDueAt",
    label: "Review by",
    render: (_v, item) => <span>{item.slaDueAt ? new Date(item.slaDueAt).toLocaleDateString() : "—"}</span>,
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
    <div className="space-y-6" data-testid="admin-erasure-requests">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Data Erasure Requests</h1>
        <p className="text-sm text-muted-foreground">
          NDPA right-to-erasure queue (§18.1). Approving then executing pseudonymises the subject&apos;s PII irreversibly (§4.11).
        </p>
      </div>

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
            options: Object.values(ErasureRequestStatus).map((s) => ({ label: s, value: s })),
          },
        ]}
        isLoading={isLoading}
        isError={isError}
        error={error as Error | null}
      />
    </div>
  );
}
