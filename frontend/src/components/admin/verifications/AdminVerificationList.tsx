"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Badge } from "@3rdparty/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@3rdparty/ui/select";
import { Column, DataTable } from "@components/ui/table/DataTable";
import { Page, PageRequest } from "@/types/models";
import { ROUTES } from "@/lib/routes";
import { VerificationStatus, VerificationTier } from "@/types/verification";
import {
  SlaHealth,
  VerificationListFilters,
  VerificationSummary,
} from "@/types/adminVerification";
import { useAdminVerificationsQuery } from "./libs/useAdminVerificationQueries";

const PAGE_SIZE = 10;
const ALL = "ALL";

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
    render: (_v, item) => <span>{item.tier ?? "—"}</span>,
  },
  {
    key: "status",
    label: "Status",
    render: (_v, item) => (
      <span className="inline-flex items-center gap-1">
        <Badge variant="outline">{item.status}</Badge>
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

export default function AdminVerificationList() {
  const router = useRouter();
  const [page, setPage] = useState(0);
  const [filters, setFilters] = useState<VerificationListFilters>({});

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

  const updateFilters = (u: Partial<PageRequest>) => {
    if (u.page !== undefined) setPage(u.page);
  };

  const setFilter = (patch: Partial<VerificationListFilters>) => {
    setPage(0);
    setFilters((f) => ({ ...f, ...patch }));
  };

  return (
    <div className="space-y-6" data-testid="admin-verifications">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-bold text-foreground">Verifications</h1>
      </div>

      <div className="flex flex-wrap gap-3">
        <Select
          value={filters.status ?? ALL}
          onValueChange={(v) =>
            setFilter({ status: v === ALL ? undefined : (v as VerificationStatus) })
          }
        >
          <SelectTrigger className="w-44" data-testid="admin-verif-status-filter">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All statuses</SelectItem>
            {Object.values(VerificationStatus).map((s) => (
              <SelectItem key={s} value={s}>
                {s}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select
          value={filters.tier ?? ALL}
          onValueChange={(v) => setFilter({ tier: v === ALL ? undefined : (v as VerificationTier) })}
        >
          <SelectTrigger className="w-40" data-testid="admin-verif-tier-filter">
            <SelectValue placeholder="Tier" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All tiers</SelectItem>
            {Object.values(VerificationTier).map((t) => (
              <SelectItem key={t} value={t}>
                {t}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select
          value={filters.overdueOnly ? "OVERDUE" : ALL}
          onValueChange={(v) => setFilter({ overdueOnly: v === "OVERDUE" })}
        >
          <SelectTrigger className="w-40" data-testid="admin-verif-overdue-filter">
            <SelectValue placeholder="SLA" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All SLA</SelectItem>
            <SelectItem value="OVERDUE">Overdue only</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <DataTable<VerificationSummary & Record<string, unknown>>
        dataPage={dataPage}
        columns={columns}
        currentPage={page}
        updateFilters={updateFilters}
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
