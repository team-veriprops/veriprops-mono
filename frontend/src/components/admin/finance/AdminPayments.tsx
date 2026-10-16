"use client";

import Link from "next/link";
import { Column, DataTable, TableFilterUpdate } from "@components/ui/table/DataTable";
import { PageShell } from "@components/ui/PageShell";
import { StatusPill } from "@components/ui/StatusPill";
import { useSyncedQueryState } from "@hooks/useSyncedQueryState";
import { useGlobalSettings } from "@stores/useGlobalSettings";
import { formatMinor, humanizeEnumLabel } from "@lib/utils";
import { ROUTES } from "@/lib/routes";
import { emptyPage, Page } from "@/types/models";
import { AdminPayment, PaymentStatus } from "@/types/verification";
import { useAdminPaymentsQuery } from "./libs/useFinanceQueries";

type Row = AdminPayment & Record<string, unknown>;

/** What happened to a charge's money after it settled, as the backend recorded it: a chargeback
 * holding it, an approved refund still owed (the gateway refused it), or what was refunded. */
export function paymentAftermath(p: AdminPayment): string {
  if (p.chargebackStatus) return `Chargeback: ${humanizeEnumLabel(p.chargebackStatus)}`;
  if (p.refundDueMinor) return `Refund owed: ${formatMinor(p.refundDueMinor, p.currency)} — retry from Finance`;
  if (p.refundedAmountMinor) return `Refunded ${formatMinor(p.refundedAmountMinor, p.currency)}`;
  return "—";
}

const columns: Column<Row>[] = [
  {
    key: "txRef",
    label: "Reference",
    render: (_v, p) => <span className="font-mono text-xs">{p.txRef}</span>,
  },
  {
    key: "vid",
    label: "Verification",
    render: (_v, p) => (
      <Link href={ROUTES.ADMIN.VERIFICATION_DETAIL(p.verificationId)} className="font-mono text-xs underline">
        {p.vid}
      </Link>
    ),
  },
  {
    key: "amountMinor",
    label: "Amount",
    render: (_v, p) => <span className="tabular-nums">{formatMinor(p.amountMinor, p.currency)}</span>,
  },
  { key: "status", label: "Status", render: (_v, p) => <StatusPill status={p.status} /> },
  {
    key: "provider",
    label: "Gateway",
    render: (_v, p) => <span>{p.provider ? humanizeEnumLabel(p.provider) : "Stub"}</span>,
  },
  { key: "aftermath", label: "Refund / chargeback", render: (_v, p) => <span>{paymentAftermath(p)}</span> },
  {
    key: "dateCreated",
    label: "Created",
    render: (_v, p) => <span>{new Date(p.dateCreated).toLocaleString()}</span>,
  },
];

interface PaymentsTableState extends Record<string, unknown> {
  page: number;
  query: string;
  status: string;
  orderBy: string;
}

/**
 * Finance's payments list (§18.1): every charge and where its money stands — settled, refunded,
 * a refund the gateway refused (still Succeeded on a closed case), or under a chargeback.
 * Search (reference or VID), the status filter, sorting and paging all run on the server.
 */
export default function AdminPayments() {
  const [tableState, updateTableState] = useSyncedQueryState<PaymentsTableState>({
    page: 0, query: "", status: "", orderBy: "",
  });
  const page = tableState.page ?? 0;
  const query = tableState.query ?? "";
  const status = (tableState.status || undefined) as PaymentStatus | undefined;
  const orderBy = tableState.orderBy || undefined;
  const pageSize = useGlobalSettings((s) => s.settings.rowsPerPage);

  const { data, isLoading, isError, error } = useAdminPaymentsQuery(
    page, { query: query || undefined, status, orderBy }, pageSize,
  );

  const dataPage = ((data as Page<Row> | null) ?? emptyPage<Row>(page, pageSize));

  const updateFilters = (u: TableFilterUpdate) => updateTableState(u as Partial<PaymentsTableState>);

  return (
    <PageShell
      title="Payments"
      description="Every charge and where its money stands: refunded, under a chargeback, or owing an approved refund the gateway refused (retry it from Finance)."
      width="wide"
      data-testid="admin-payments"
    >
      <DataTable<Row>
        dataPage={dataPage}
        columns={columns}
        currentPage={page}
        orderBy={orderBy}
        searchValue={query}
        updateFilters={updateFilters}
        filters={[
          {
            key: "status",
            label: "Status",
            value: tableState.status ?? "",
            options: Object.values(PaymentStatus).map((s) => ({ label: humanizeEnumLabel(s), value: s })),
          },
        ]}
        isLoading={isLoading}
        isError={isError}
        error={error as Error | null}
      />
    </PageShell>
  );
}
