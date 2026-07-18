"use client";

import { useRouter } from "next/navigation";
import { DEFAULT_PAGE_SIZE } from "@lib/config/app";
import { Badge } from "@3rdparty/ui/badge";
import { Column, DataTable, TableFilterUpdate } from "@components/ui/table/DataTable";
import { StatusPill } from "@components/ui/StatusPill";
import { useSyncedQueryState } from "@hooks/useSyncedQueryState";
import { humanizeEnumLabel } from "@lib/utils";
import { ROUTES } from "@lib/routes";
import { AdminUserSummary } from "@/types/admin";
import {
  AccountStatus,
  TrustStatus,
  UserPersona,
  UserType,
} from "@components/website/auth/models";
import { useAdminUsersQuery } from "@components/admin/libs/useAdminUsersQueries";

const columns: Column<AdminUserSummary & Record<string, unknown>>[] = [
  { key: "name", label: "Name" },
  { key: "email", label: "Email" },
  {
    key: "personas",
    label: "Personas",
    render: (_v, item) =>
      item.personas.length ? (
        <span className="flex flex-wrap gap-1">
          {item.personas.map((p) => (
            <Badge key={p} variant="secondary">
              {humanizeEnumLabel(p)}
            </Badge>
          ))}
        </span>
      ) : (
        "—"
      ),
  },
  {
    key: "userType",
    label: "Type",
    render: (_v, item) => humanizeEnumLabel(item.userType),
  },
  {
    key: "trustStatus",
    label: "Trust",
    render: (_v, item) => <StatusPill status={item.trustStatus} />,
  },
  {
    key: "accountStatus",
    label: "Account",
    render: (_v, item) => <StatusPill status={item.accountStatus} />,
  },
  {
    key: "dateCreated",
    label: "Joined",
    render: (_v, item) => new Date(item.dateCreated).toLocaleDateString(),
  },
];

const PAGE_SIZE = DEFAULT_PAGE_SIZE;

interface UsersTableState extends Record<string, unknown> {
  page: number;
  query: string;
  persona: string;
  userType: string;
  trustStatus: string;
  accountStatus: string;
}

export default function AdminUsersManagement() {
  const router = useRouter();
  const [tableState, updateTableState] = useSyncedQueryState<UsersTableState>({
    page: 0,
    query: "",
    persona: "",
    userType: "",
    trustStatus: "",
    accountStatus: "",
  });
  const page = tableState.page ?? 0;
  const query = tableState.query ?? "";
  const persona = tableState.persona ?? "";
  const userType = tableState.userType ?? "";
  const trustStatus = tableState.trustStatus ?? "";
  const accountStatus = tableState.accountStatus ?? "";

  const { data: pageData, isLoading, isError, error } = useAdminUsersQuery({
    page,
    pageSize: PAGE_SIZE,
    query: query || undefined,
    persona: persona || undefined,
    userType: userType || undefined,
    trustStatus: trustStatus || undefined,
    accountStatus: accountStatus || undefined,
  });

  const updateFilters = (updates: TableFilterUpdate) => {
    updateTableState(updates as Partial<UsersTableState>);
  };

  const emptyPage = {
    status: "success",
    code: "200",
    items: [] as (AdminUserSummary & Record<string, unknown>)[],
    meta: { page: 0, pageSize: PAGE_SIZE, count: 0, total: 0, totalPages: 0 },
  };

  return (
    <div className="space-y-6" data-testid="admin-users">
      <h1 className="text-2xl font-bold text-foreground">Users</h1>

      <DataTable<AdminUserSummary & Record<string, unknown>>
        dataPage={(pageData as typeof emptyPage) ?? emptyPage}
        columns={columns}
        currentPage={page}
        updateFilters={updateFilters}
        searchValue={query}
        filters={[
          {
            key: "persona",
            label: "Persona",
            value: persona,
            options: Object.values(UserPersona).map((p) => ({
              label: humanizeEnumLabel(p),
              value: p,
            })),
          },
          {
            key: "userType",
            label: "Type",
            value: userType,
            options: Object.values(UserType).map((t) => ({
              label: humanizeEnumLabel(t),
              value: t,
            })),
          },
          {
            key: "trustStatus",
            label: "Trust",
            value: trustStatus,
            options: Object.values(TrustStatus).map((t) => ({
              label: humanizeEnumLabel(t),
              value: t,
            })),
          },
          {
            key: "accountStatus",
            label: "Account",
            value: accountStatus,
            options: Object.values(AccountStatus).map((s) => ({
              label: humanizeEnumLabel(s),
              value: s,
            })),
          },
        ]}
        isLoading={isLoading}
        isError={isError}
        error={error as Error | null}
        isRowClickable
        onRowClick={(row) => router.push(ROUTES.ADMIN.USER_DETAIL(row.id))}
        searchPlaceholder="Search by name, email or phone…"
      />
    </div>
  );
}
