"use client";

import { Column, DataTable, TableFilterUpdate } from "@components/ui/table/DataTable";
import { useSyncedQueryState } from "@hooks/useSyncedQueryState";
import { Page } from "@/types/models";
import { ADMIN_ACTION_TYPES, AuditPackRow } from "@/types/audit";
import { useAdminActionsQuery } from "./libs/useAuditQueries";

const PAGE_SIZE = 20;

function humanize(text: string): string {
  return text.toLowerCase().split("_").map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
}

const columns: Column<AuditPackRow & Record<string, unknown>>[] = [
  {
    key: "occurredAt",
    label: "When",
    render: (_v, item) => <span>{new Date(item.occurredAt).toLocaleString()}</span>,
  },
  { key: "action", label: "Action", render: (_v, item) => <span>{humanize(item.action)}</span> },
  { key: "resourceType", label: "Resource" },
  {
    key: "actorId",
    label: "Actor",
    render: (_v, item) => (
      <span className="font-mono text-xs">{item.actorId ?? "system"}</span>
    ),
  },
  {
    key: "ipAddress",
    label: "IP",
    render: (_v, item) => <span className="font-mono text-xs">{item.ipAddress ?? "—"}</span>,
  },
];

interface AuditTableState extends Record<string, unknown> {
  page: number;
  action: string;
}

export default function AdminAuditLog() {
  const [tableState, updateTableState] = useSyncedQueryState<AuditTableState>({ page: 0, action: "" });
  const page = tableState.page ?? 0;
  const action = tableState.action ?? "";

  const { data, isLoading, isError, error } = useAdminActionsQuery(page, action || undefined);

  const total = data?.total ?? 0;
  const totalPages = total ? Math.ceil(total / PAGE_SIZE) : 0;
  const dataPage: Page<AuditPackRow & Record<string, unknown>> = {
    status: "success",
    code: "200",
    items: (data?.items ?? []) as (AuditPackRow & Record<string, unknown>)[],
    meta: {
      page,
      pageSize: PAGE_SIZE,
      count: data?.items?.length ?? 0,
      total,
      totalPages,
      prevPage: page > 0 ? page - 1 : undefined,
      nextPage: page + 1 < totalPages ? page + 1 : undefined,
    },
  };

  const updateFilters = (u: TableFilterUpdate) => updateTableState(u as Partial<AuditTableState>);

  return (
    <div className="space-y-6" data-testid="admin-audit-log">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Admin Audit Log</h1>
          <p className="text-sm text-muted-foreground">
            Privileged admin actions — role changes, config edits, approvals, and NDPA erasures (§19.6).
          </p>
        </div>
      </div>

      <DataTable<AuditPackRow & Record<string, unknown>>
        dataPage={dataPage}
        columns={columns}
        currentPage={page}
        updateFilters={updateFilters}
        filters={[
          {
            key: "action",
            label: "Action",
            value: action,
            options: ADMIN_ACTION_TYPES.map((a) => ({ label: humanize(a), value: a })),
          },
        ]}
        isLoading={isLoading}
        isError={isError}
        error={error as Error | null}
      />
    </div>
  );
}
