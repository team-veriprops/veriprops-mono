"use client";

import { useState } from "react";
import { toast } from "sonner";
import { CheckCircle2, Trash2 } from "lucide-react";
import { Button } from "@3rdparty/ui/button";
import { Input } from "@3rdparty/ui/input";
import { Label } from "@3rdparty/ui/label";
import { Card } from "@3rdparty/ui/card";
import { AsyncStateComponent } from "@components/ui/AsyncStateComponent";
import { formatMinor } from "@lib/utils";
import { BankAccount, Payout, PayoutQuote, ResolvedBankAccount } from "@/types/payout";
import { Page } from "@/types/models";
import {
  useAddBankAccountMutation,
  useBankAccountsQuery,
  useBanksQuery,
  useCancelPayoutMutation,
  usePayoutsQuery,
  useQuotePayoutMutation,
  useRemoveBankAccountMutation,
  useRequestPayoutMutation,
  useResolveBankAccountMutation,
} from "./libs/usePayoutQueries";
import { PayoutHistoryItem } from "./PayoutHistoryItem";
import { getErrorMessage } from "@lib/errors";

/** A Nigerian NUBAN: exactly ten digits (the backend enforces the same). */
const ACCOUNT_NUMBER_LENGTH = 10;

/** Agent payouts (§15.1): withdraw to a saved account the bank has confirmed, net of the
 * transfer fee, and see withdrawal history. */
export default function AgentPayouts() {
  return (
    <div className="mx-auto max-w-3xl space-y-6 p-4 sm:p-6">
      <header>
        <h1 className="text-lg font-semibold">Withdrawals</h1>
        <p className="text-sm text-muted-foreground">
          Withdraw your available balance. Once finance approves a withdrawal, it is sent to your bank in the next payout run.
        </p>
      </header>
      <RequestWithdrawal />
      <BankAccounts />
      <PayoutHistory />
    </div>
  );
}

function RequestWithdrawal() {
  const banks = useBankAccountsQuery();
  const quote = useQuotePayoutMutation();
  const request = useRequestPayoutMutation();
  const [amount, setAmount] = useState("");
  const [bankAccountId, setBankAccountId] = useState("");
  // The quote the agent is confirming; any edit sends them back to review.
  const [review, setReview] = useState<PayoutQuote | null>(null);

  const amountMinor = Math.round(Number(amount) * 100);

  const startReview = () => {
    if (!amountMinor || amountMinor <= 0) {
      toast.error("Enter a valid amount.");
      return;
    }
    if (!bankAccountId) {
      toast.error("Select a bank account.");
      return;
    }
    quote.mutate(
      { amountMinor, bankAccountId },
      {
        onSuccess: (res) => setReview(res.data ?? null),
        onError: (e: unknown) => toast.error(getErrorMessage(e, "Could not work out the transfer fee.")),
      },
    );
  };

  const confirm = () => {
    request.mutate(
      { amountMinor, bankAccountId },
      {
        onSuccess: () => {
          toast.success("Withdrawal requested.");
          setAmount("");
          setReview(null);
        },
        onError: (e: unknown) => toast.error(getErrorMessage(e, "Could not request the withdrawal.")),
      },
    );
  };

  return (
    <Card className="space-y-3 p-4">
      <h2 className="text-sm font-semibold">Request a withdrawal</h2>
      <div className="space-y-2">
        <Label htmlFor="payout-amount">Amount (₦)</Label>
        <Input id="payout-amount" inputMode="decimal" value={amount}
          onChange={(e) => { setAmount(e.target.value); setReview(null); }}
          placeholder="0.00" data-testid="payout-amount" />
      </div>
      <div className="space-y-2">
        <Label htmlFor="payout-bank">Bank account</Label>
        <select id="payout-bank" value={bankAccountId}
          onChange={(e) => { setBankAccountId(e.target.value); setReview(null); }}
          className="h-9 w-full rounded-md border bg-background px-3 text-sm" data-testid="payout-bank">
          <option value="">Select an account…</option>
          {(banks.data ?? []).map((a) => (
            <option key={a.id} value={a.id}>
              {a.bankName} · {a.accountNumber} ({a.accountName})
            </option>
          ))}
        </select>
        {(banks.data ?? []).length === 0 && (
          <p className="text-xs text-muted-foreground">Add a bank account below first.</p>
        )}
      </div>

      {review ? (
        <div className="space-y-3 rounded-lg border p-3 text-sm" data-testid="payout-review">
          <dl className="grid grid-cols-2 gap-y-1">
            <dt className="text-muted-foreground">Withdrawal</dt>
            <dd className="text-right tabular-nums">{formatMinor(review.amountMinor)}</dd>
            <dt className="text-muted-foreground">Transfer fee</dt>
            <dd className="text-right tabular-nums" data-testid="payout-quote-fee">−{formatMinor(review.feeMinor)}</dd>
            <dt className="font-medium">You&apos;ll receive</dt>
            <dd className="text-right font-semibold tabular-nums" data-testid="payout-quote-net">{formatMinor(review.netMinor)}</dd>
          </dl>
          <div className="flex flex-col gap-2 sm:flex-row">
            <Button onClick={confirm} disabled={request.isPending} data-testid="payout-submit">
              Confirm withdrawal
            </Button>
            <Button variant="ghost" onClick={() => setReview(null)}>Change</Button>
          </div>
        </div>
      ) : (
        <Button onClick={startReview} disabled={quote.isPending} data-testid="payout-review-btn">
          Review withdrawal
        </Button>
      )}
    </Card>
  );
}

function BankAccounts() {
  const accounts = useBankAccountsQuery();
  const banks = useBanksQuery();
  const resolve = useResolveBankAccountMutation();
  const add = useAddBankAccountMutation();
  const remove = useRemoveBankAccountMutation();
  const [bankCode, setBankCode] = useState("");
  const [accountNumber, setAccountNumber] = useState("");
  // The account as the bank holds it; saving is offered only once the bank has named it.
  const [resolved, setResolved] = useState<ResolvedBankAccount | null>(null);

  const complete = bankCode !== "" && accountNumber.length === ACCOUNT_NUMBER_LENGTH;

  const check = () => {
    resolve.mutate(
      { bankCode, accountNumber },
      {
        onSuccess: (res) => setResolved(res.data ?? null),
        onError: (err) => toast.error(getErrorMessage(err, "Could not check the account with the bank.")),
      },
    );
  };

  const save = () => {
    add.mutate({ bankCode, accountNumber }, {
      onSuccess: () => {
        toast.success("Bank account saved.");
        setBankCode("");
        setAccountNumber("");
        setResolved(null);
      },
      onError: (err) => toast.error(getErrorMessage(err, "Could not save the account.")),
    });
  };

  return (
    <Card className="space-y-3 p-4">
      <h2 className="text-sm font-semibold">Bank accounts</h2>
      <AsyncStateComponent<BankAccount[]>
        isLoading={accounts.isLoading}
        isError={accounts.isError}
        data={accounts.data}
        loadingText="Loading accounts…"
        emptyText="No saved accounts."
      >
        {(list) =>
          list.length === 0 ? (
            <p className="text-sm text-muted-foreground">No saved accounts yet.</p>
          ) : (
            <ul className="divide-y rounded-lg border" data-testid="bank-accounts">
              {list.map((a) => (
                <li key={a.id} className="flex items-center justify-between gap-2 p-3 text-sm">
                  <span className="truncate">
                    {a.bankName} · {a.accountNumber} · {a.accountName}
                    {a.isDefault && <span className="ml-2 text-xs text-emerald-600">default</span>}
                  </span>
                  <button aria-label="Remove account" className="text-muted-foreground hover:text-red-600"
                    onClick={() => remove.mutate(a.id)}>
                    <Trash2 className="size-4" />
                  </button>
                </li>
              ))}
            </ul>
          )
        }
      </AsyncStateComponent>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        <select aria-label="Bank" value={bankCode}
          onChange={(e) => { setBankCode(e.target.value); setResolved(null); }}
          className="h-9 w-full rounded-md border bg-background px-3 text-sm" data-testid="bank-name">
          <option value="">{banks.isLoading ? "Loading banks…" : "Select your bank…"}</option>
          {(banks.data ?? []).map((b) => <option key={b.code} value={b.code}>{b.name}</option>)}
        </select>
        <Input aria-label="Account number" placeholder="10-digit account number" inputMode="numeric"
          maxLength={ACCOUNT_NUMBER_LENGTH} value={accountNumber}
          onChange={(e) => { setAccountNumber(e.target.value.replace(/\D/g, "")); setResolved(null); }}
          data-testid="bank-number" />
      </div>

      {resolved ? (
        <div className="space-y-2">
          <p className="flex items-center gap-2 rounded-md border bg-muted/40 p-2 text-sm" data-testid="bank-resolved-name">
            <CheckCircle2 className="size-4 text-emerald-600" aria-hidden />
            <span><span className="text-muted-foreground">Account name: </span>{resolved.accountName}</span>
          </p>
          <p className="text-xs text-muted-foreground">
            This is the name your bank holds. Payouts go only to accounts in your own name.
          </p>
          <Button variant="outline" size="sm" onClick={save} disabled={add.isPending} data-testid="bank-add">
            Save account
          </Button>
        </div>
      ) : (
        <Button variant="outline" size="sm" onClick={check} disabled={!complete || resolve.isPending}
          data-testid="bank-verify">
          Check account
        </Button>
      )}
    </Card>
  );
}

function PayoutHistory() {
  const [page, setPage] = useState(0);
  const { data, isLoading, isError } = usePayoutsQuery(page);
  const cancel = useCancelPayoutMutation();

  return (
    <section className="space-y-2">
      <h2 className="text-sm font-semibold">History</h2>
      <AsyncStateComponent<Page<Payout>>
        isLoading={isLoading}
        isError={isError}
        data={data}
        loadingText="Loading history…"
        emptyText="No withdrawals yet."
      >
        {(pageData) => (
          <>
            {pageData.items.length === 0 ? (
              <p className="text-sm text-muted-foreground">No withdrawals yet.</p>
            ) : (
              <ul className="divide-y rounded-lg border" data-testid="payout-history">
                {pageData.items.map((p) => (
                  <PayoutHistoryItem key={p.id} payout={p} onCancel={() => cancel.mutate(p.id)} />
                ))}
              </ul>
            )}
            <div className="mt-3 flex items-center justify-between">
              <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage((p) => Math.max(0, p - 1))}>
                Previous
              </Button>
              <span className="text-xs text-muted-foreground">Page {page + 1}</span>
              <Button variant="outline" size="sm" disabled={pageData.meta.nextPage == null} onClick={() => setPage((p) => p + 1)}>
                Next
              </Button>
            </div>
          </>
        )}
      </AsyncStateComponent>
    </section>
  );
}
