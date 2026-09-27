"use client";

import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";
import { Undo2 } from "lucide-react";
import { Button } from "@3rdparty/ui/button";
import { Card } from "@3rdparty/ui/card";
import ListPager from "@components/ui/ListPager";
import { getErrorMessage } from "@lib/errors";
import { ROUTES } from "@lib/routes";
import { formatMinor } from "@lib/utils";
import { useRefundRetriesQuery, useRetryRefundMutation } from "./libs/useFinanceQueries";

/**
 * Refunds a payment gateway refused (§8.5). The payment is still settled while its
 * verification was failed or refunded, so the customer is owed the money. Finance retries it
 * here. An admin without REFUND_PAYMENT is refused the list by the backend and sees nothing.
 */
export default function RefundRetries() {
  const [page, setPage] = useState(0);
  const { data, isError } = useRefundRetriesQuery(page);
  const retry = useRetryRefundMutation();

  if (isError || !data) return null;

  const onRetry = (paymentId: string) =>
    retry.mutate(paymentId, {
      onSuccess: () => toast.success("Refund sent to the gateway."),
      onError: (err) => toast.error(getErrorMessage(err, "The gateway declined the refund again.")),
    });

  return (
    <Card className="space-y-4 p-6" data-testid="refund-retries">
      <div className="flex items-center gap-2">
        <Undo2 className="size-4" aria-hidden />
        <h2 className="text-sm font-semibold">Refunds to retry</h2>
      </div>
      {data.items.length === 0 ? (
        <p className="text-sm text-muted-foreground" data-testid="refund-retries-empty">
          No refunds are waiting. Every refund the gateways accepted has gone through.
        </p>
      ) : (
        <ul className="divide-y divide-border">
          {data.items.map((payment) => (
            <li
              key={payment.id}
              className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between"
              data-testid={`refund-retry-${payment.id}`}
            >
              <div className="min-w-0">
                <p className="truncate font-mono text-sm">{payment.txRef}</p>
                <Link
                  href={ROUTES.ADMIN.VERIFICATION_DETAIL(payment.verificationId)}
                  className="text-xs text-muted-foreground underline"
                >
                  Open verification
                </Link>
              </div>
              <div className="flex items-center gap-3">
                <span className="tabular-nums text-sm">
                  {formatMinor(payment.chargeAmountMinor ?? payment.amountMinor, payment.chargeCurrency ?? payment.currency)}
                </span>
                <Button
                  size="sm"
                  onClick={() => onRetry(payment.id)}
                  disabled={retry.isPending}
                  data-testid={`refund-retry-${payment.id}-submit`}
                >
                  Retry refund
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}
      <ListPager page={page} totalPages={data.meta.totalPages} onPageChange={setPage} testIdPrefix="refund-retries" />
    </Card>
  );
}
