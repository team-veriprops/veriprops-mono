"use client";

import { Column, DataTable, TableFilterUpdate } from "@components/ui/table/DataTable";
import { PageShell } from "@components/ui/PageShell";
import { useSyncedQueryState } from "@hooks/useSyncedQueryState";
import { useGlobalSettings } from "@stores/useGlobalSettings";
import { humanizeEnumLabel } from "@lib/utils";
import { emptyPage, Page } from "@/types/models";
import { ADMIN_ACTION_TYPES, AuditPackRow } from "@/types/audit";
import { useAdminActionsQuery } from "./libs/useAuditQueries";

const columns: Column<AuditPackRow & Record<string, unknown>>[] = [
  {
    key: "occurredAt",
    label: "When",
    render: (_v, item) => <span>{new Date(item.occurredAt).toLocaleString()}</span>,
  },
  { key: "action", label: "Action", render: (_v, item) => <span>{humanizeEnumLabel(item.action)}</span> },
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
  orderBy: string;
}

export default function AdminAuditLog() {
  const [tableState, updateTableState] = useSyncedQueryState<AuditTableState>({ page: 0, action: "", orderBy: "" });
  const page = tableState.page ?? 0;
  const action = tableState.action ?? "";
  const orderBy = tableState.orderBy ?? "";
  const pageSize = useGlobalSettings((s) => s.settings.rowsPerPage);

  const { data, isLoading, isError, error } = useAdminActionsQuery(
    page, pageSize, action || undefined, orderBy || undefined,
  );
  const dataPage = (data ?? emptyPage(page, pageSize)) as Page<AuditPackRow & Record<string, unknown>>;

  const updateFilters = (u: TableFilterUpdate) => updateTableState(u as Partial<AuditTableState>);

  return (
    <PageShell
      title="Admin Audit Log"
      description="Privileged admin actions — role changes, config edits, approvals, and NDPA erasures (§19.6)."
      width="wide"
      data-testid="admin-audit-log"
    >
      <DataTable<AuditPackRow & Record<string, unknown>>
        dataPage={dataPage}
        columns={columns}
        currentPage={page}
        orderBy={orderBy || undefined}
        updateFilters={updateFilters}
        filters={[
          {
            key: "action",
            label: "Action",
            value: action,
            options: ADMIN_ACTION_TYPES.map((a) => ({ label: humanizeEnumLabel(a), value: a })),
          },
        ]}
        isLoading={isLoading}
        isError={isError}
        error={error as Error | null}
      />
    </PageShell>
  );
}
