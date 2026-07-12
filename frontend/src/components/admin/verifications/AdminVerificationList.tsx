"use client";

import { useRouter } from "next/navigation";
import { DEFAULT_PAGE_SIZE } from "@lib/config/app";
import { Badge } from "@3rdparty/ui/badge";
import { Column, DataTable, TableFilterUpdate } from "@components/ui/table/DataTable";
import { VerificationStatusBadge } from "@components/portal/verifications/VerificationStatusBadge";
import { useSyncedQueryState } from "@hooks/useSyncedQueryState";
import { humanizeEnumLabel } from "@lib/utils";
import { Page } from "@/types/models";
import { ROUTES } from "@/lib/routes";
import { VerificationStatus, VerificationTier } from "@/types/verification";
import {
  SlaHealth,
  VerificationListFilters,
  VerificationSummary,
} from "@/types/adminVerification";
import { useAdminVerificationsQuery } from "./libs/useAdminVerificationQueries";

const PAGE_SIZE = DEFAULT_PAGE_SIZE;
// Sentinel used in table state to mean "overdue filter on".
const OVERDUE = "OVERDUE";

const SLA_VARIANT: Record<SlaHealth, "default" | "secondary" | "destructive" | "outline"> = {
  [SlaHealth.ON_TRACK]: "secondary",
  [SlaHealth.AT_RISK]: "default",
  [SlaHealth.OVERDUE]: "destructive",
  [SlaHealth.NONE]: "outline",
};

const SlaBadge = ({ item }: { item: VerificationSummary }) => {
  if (item.slaHealth === SlaHealth.NONE) return <span className="text-muted-foreground">—</span>;
  const label =
    item.slaHealth === SlaHealth.OVERDUE
      ? `Overdue ${Math.abs(item.businessDaysRemaining ?? 0)}d`
      : `${item.businessDaysRemaining ?? 0}d left`;
  return <Badge variant={SLA_VARIANT[item.slaHealth]}>{label}</Badge>;
};

const columns: Column<VerificationSummary & Record<string, unknown>>[] = [
  { key: "vid", label: "VID" },
  {
    key: "tier",
    label: "Tier",
    render: (_v, item) => <span>{item.tier ? humanizeEnumLabel(item.tier) : "—"}</span>,
  },
  {
    key: "status",
    label: "Status",
    render: (_v, item) => (
      <span className="inline-flex items-center gap-1">
        <VerificationStatusBadge status={item.status} />
        {item.paused && <Badge variant="destructive">Paused</Badge>}
      </span>
    ),
  },
  {
    key: "stateRegion",
    label: "Region",
    render: (_v, item) => <span>{item.stateRegion ?? "—"}</span>,
  },
  {
    key: "slaHealth",
    label: "SLA",
    render: (_v, item) => <SlaBadge item={item} />,
  },
];

interface VerificationTableState extends Record<string, unknown> {
  page: number;
  query: string;
  status: string;
  tier: string;
  overdue: string;
}

export default function AdminVerificationList() {
  const router = useRouter();
  const [tableState, updateTableState] = useSyncedQueryState<VerificationTableState>({
    page: 0,
    query: "",
    status: "",
    tier: "",
    overdue: "",
  });
  const page = tableState.page ?? 0;
  const query = tableState.query ?? "";
  const status = tableState.status ?? "";
  const tier = tableState.tier ?? "";
  const overdue = tableState.overdue ?? "";

  const filters: VerificationListFilters = {
    status: status ? (status as VerificationStatus) : undefined,
    tier: tier ? (tier as VerificationTier) : undefined,
    overdueOnly: overdue === OVERDUE,
    query: query || undefined,
  };

  const { data, isLoading, isError, error } = useAdminVerificationsQuery(filters, page, PAGE_SIZE);

  const dataPage: Page<VerificationSummary & Record<string, unknown>> = (data as
    | Page<VerificationSummary & Record<string, unknown>>
    | null) ?? {
    status: "success",
    code: "200",
    items: [],
    meta: {
      page,
      pageSize: PAGE_SIZE,
      count: 0,
      total: 0,
      totalPages: 0,
    },
  };

  const updateFilters = (u: TableFilterUpdate) => {
    updateTableState(u as Partial<VerificationTableState>);
  };

  return (
    <div className="space-y-6" data-testid="admin-verifications">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-bold text-foreground">Verifications</h1>
      </div>

      <DataTable<VerificationSummary & Record<string, unknown>>
        dataPage={dataPage}
        columns={columns}
        currentPage={page}
        updateFilters={updateFilters}
        searchValue={query}
        filters={[
          {
            key: "status",
            label: "Status",
            value: status,
            options: Object.values(VerificationStatus).map((s) => ({ label: s, value: s })),
          },
          {
            key: "tier",
            label: "Tier",
            value: tier,
            options: Object.values(VerificationTier).map((t) => ({ label: t, value: t })),
          },
          {
            key: "overdue",
            label: "SLA",
            value: overdue,
            options: [{ label: "Overdue only", value: OVERDUE }],
          },
        ]}
        isLoading={isLoading}
        isError={isError}
        error={error as Error | null}
        isRowClickable
        onRowClick={(row) => router.push(ROUTES.ADMIN.VERIFICATION_DETAIL(row.id))}
        searchPlaceholder="Search by VID…"
      />
    </div>
  );
}
