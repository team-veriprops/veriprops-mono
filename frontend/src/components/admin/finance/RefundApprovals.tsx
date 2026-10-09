"use client";

import { useId, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { Button } from "@3rdparty/ui/button";
import { Label } from "@3rdparty/ui/label";
import { Textarea } from "@3rdparty/ui/textarea";
import { getErrorMessage } from "@lib/errors";
import { formatMinor, humanizeEnumLabel } from "@lib/utils";
import { ROUTES } from "@/lib/routes";
import { Column, DataTable, TableFilterUpdate } from "@components/ui/table/DataTable";
import DetailDrawer from "@components/ui/DetailDrawer";
import { ConfirmDialog } from "@components/ui/ConfirmDialog";
import { PageShell } from "@components/ui/PageShell";
import { StatusPill } from "@components/ui/StatusPill";
import { useSyncedQueryState } from "@hooks/useSyncedQueryState";
import { useGlobalSettings } from "@stores/useGlobalSettings";
import { emptyPage, Page } from "@/types/models";
import { RefundRequest, RefundRequestStatus, RefundSource } from "@/types/closure";
import { CLOSE_REASONS } from "@components/admin/verifications/libs/closure";
import { refundSummary } from "@components/admin/verifications/libs/refundSummary";
import { useApproveRefundMutation, useRefundRequestsQuery, useRejectRefundMutation } from "./libs/useFinanceQueries";

type Row = RefundRequest & Record<string, unknown>;

const SOURCE_LABELS: Record<RefundSource, string> = {
  [RefundSource.CASE_CLOSURE]: "Case closed",
  [RefundSource.DISPUTE_UPHELD]: "Dispute upheld",
  [RefundSource.LATE_CHARGE]: "Charge after the case closed",
};

/** Why the money is going back, in words: the close reason, or the source itself. */
export function refundReasonLabel(r: RefundRequest): string {
  const reason = CLOSE_REASONS.find((c) => c.value === r.reason)?.label;
  return reason ? `${SOURCE_LABELS[r.source]}: ${reason.toLowerCase()}` : SOURCE_LABELS[r.source];
}

const columns: Column<Row>[] = [
  {
    key: "vid",
    label: "Verification",
    render: (_v, r) => (
      <Link href={ROUTES.ADMIN.VERIFICATION_DETAIL(r.verificationId)} className="font-mono text-xs underline"
        onClick={(e) => e.stopPropagation()}>
        {r.vid}
      </Link>
    ),
  },
  { key: "amountMinor", label: "Refund", render: (_v, r) => <span className="tabular-nums">{formatMinor(r.amountMinor, r.currency)}</span> },
  { key: "reason", label: "Why", render: (_v, r) => <span>{refundReasonLabel(r)}</span> },
  { key: "status", label: "Status", render: (_v, r) => <StatusPill status={r.status} /> },
  { key: "dateCreated", label: "Requested", render: (_v, r) => <span>{new Date(r.dateCreated).toLocaleString()}</span> },
];

interface RefundTableState extends Record<string, unknown> {
  page: number;
  status: string;
  orderBy: string;
}

/**
 * Finance's refund approvals (§8.5, §18.1): every return of a customer's money waits here —
 * a closed case, an upheld dispute, a charge that landed after a case closed. Approving sends
 * it through the payment gateway; rejecting sends nothing and puts a closing case back to work.
 */
export default function RefundApprovals() {
  const [tableState, updateTableState] = useSyncedQueryState<RefundTableState>({
    page: 0, status: RefundRequestStatus.PENDING, orderBy: "",
  });
  const page = tableState.page ?? 0;
  const status = (tableState.status || undefined) as RefundRequestStatus | undefined;
  const orderBy = tableState.orderBy || undefined;
  const pageSize = useGlobalSettings((s) => s.settings.rowsPerPage);
  const { data, isLoading, isError, error } = useRefundRequestsQuery(page, status, pageSize, orderBy);
  const [selected, setSelected] = useState<RefundRequest | null>(null);

  const dataPage = (data as Page<Row> | null) ?? emptyPage<Row>(page, pageSize);
  const updateFilters = (u: TableFilterUpdate) => updateTableState(u as Partial<RefundTableState>);

  return (
    <PageShell
      title="Refund approvals"
      description="No customer money leaves until Finance approves it here. Approving sends the refund through the payment gateway; rejecting sends nothing."
      width="wide"
      data-testid="refund-approvals"
    >
      <DataTable<Row>
        dataPage={dataPage}
        columns={columns}
        currentPage={page}
        orderBy={orderBy}
        updateFilters={updateFilters}
        filters={[{
          key: "status", label: "Status", value: tableState.status ?? "",
          options: Object.values(RefundRequestStatus).map((s) => ({ label: humanizeEnumLabel(s), value: s })),
        }]}
        isRowClickable
        onRowClick={(row) => setSelected(row)}
        isLoading={isLoading}
        isError={isError}
        error={error as Error | null}
      />
      {selected && <RefundDecisionDrawer request={selected} onClose={() => setSelected(null)} />}
    </PageShell>
  );
}

function RefundDecisionDrawer({ request, onClose }: { request: RefundRequest; onClose: () => void }) {
  const [note, setNote] = useState("");
  const [confirming, setConfirming] = useState(false);
  const noteId = useId();
  const approve = useApproveRefundMutation();
  const reject = useRejectRefundMutation();
  const pending = request.status === RefundRequestStatus.PENDING;
  const amount = formatMinor(request.amountMinor, request.currency);

  const onApprove = async () => {
    try {
      const res = await approve.mutateAsync({ id: request.id, note: note.trim() || undefined });
      const summary = refundSummary("Refund approved", res.data?.outcome);
      (summary.ok ? toast.success : toast.warning)(summary.message);
      onClose();
    } catch (err) {
      toast.error(getErrorMessage(err, "The refund could not be approved."));
    } finally {
      setConfirming(false);
    }
  };

  const onReject = async () => {
    try {
      await reject.mutateAsync({ id: request.id, note: note.trim() });
      toast.success(request.source === RefundSource.CASE_CLOSURE
        ? "Refund rejected. The case is back to work and its agents are told to resume."
        : "Refund rejected. Nothing was sent.");
      onClose();
    } catch (err) {
      toast.error(getErrorMessage(err, "The refund could not be rejected."));
    }
  };

  return (
    <>
      <DetailDrawer title="Refund request" reference={request.vid} open onOpenChange={(o) => !o && onClose()}
        description={refundReasonLabel(request)}>
        <div className="space-y-4 text-sm" data-testid="refund-request">
          <dl className="grid grid-cols-2 gap-x-3 gap-y-1">
            <dt className="text-muted-foreground">Refund</dt>
            <dd className="font-semibold tabular-nums" data-testid="refund-request-amount">{amount}</dd>
            <dt className="text-muted-foreground">Status</dt>
            <dd><StatusPill status={request.status} /></dd>
            {request.note && (<><dt className="text-muted-foreground">Requester&apos;s note</dt><dd>{request.note}</dd></>)}
            {request.evidenceRef && (<><dt className="text-muted-foreground">Evidence</dt><dd>{request.evidenceRef}</dd></>)}
            {request.decisionNote && (<><dt className="text-muted-foreground">Decision</dt><dd>{request.decisionNote}</dd></>)}
          </dl>
          {pending && (
            <>
              <div className="space-y-1">
                <Label htmlFor={noteId}>Your note</Label>
                <Textarea id={noteId} value={note} onChange={(e) => setNote(e.target.value)} rows={3}
                  placeholder="Required to reject: the requester is told why." data-testid="refund-request-note" />
              </div>
              <div className="flex flex-col gap-2 sm:flex-row">
                <Button className="flex-1" onClick={() => setConfirming(true)} disabled={approve.isPending || reject.isPending}
                  data-testid="refund-request-approve">
                  Approve {amount} refund
                </Button>
                <Button className="flex-1" variant="outline" onClick={onReject}
                  disabled={!note.trim() || approve.isPending || reject.isPending} data-testid="refund-request-reject">
                  Reject
                </Button>
              </div>
            </>
          )}
        </div>
      </DetailDrawer>
      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title={`Send ${amount} back to the customer?`}
        description={
          `This refunds ${amount} through the payment gateway and cannot be undone.` +
          (request.source === RefundSource.CASE_CLOSURE
            ? " The case closes for good: submitted work is paid and every other task is cancelled."
            : "")
        }
        confirmLabel={`Approve ${amount} refund`}
        onConfirm={onApprove}
        pending={approve.isPending}
        testId="refund-request-confirm"
      />
    </>
  );
}
