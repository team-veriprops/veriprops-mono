"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Trash2 } from "lucide-react";
import { Button } from "@3rdparty/ui/button";
import { Input } from "@3rdparty/ui/input";
import { Label } from "@3rdparty/ui/label";
import { Card } from "@3rdparty/ui/card";
import { AsyncStateComponent } from "@components/ui/AsyncStateComponent";
import { formatMinor } from "@lib/utils";
import { BankAccount, Payout, PayoutStatus } from "@/types/payout";
import { Page } from "@/types/models";
import {
  useAddBankAccountMutation,
  useBankAccountsQuery,
  useCancelPayoutMutation,
  usePayoutsQuery,
  useRemoveBankAccountMutation,
  useRequestPayoutMutation,
} from "./libs/usePayoutQueries";

const STATUS_TONE: Record<PayoutStatus, string> = {
  [PayoutStatus.REQUESTED]: "text-amber-600 dark:text-amber-400",
  [PayoutStatus.APPROVED]: "text-emerald-600 dark:text-emerald-400",
  [PayoutStatus.HELD]: "text-amber-600 dark:text-amber-400",
  [PayoutStatus.PAID]: "text-emerald-600 dark:text-emerald-400",
  [PayoutStatus.REJECTED]: "text-red-600 dark:text-red-400",
  [PayoutStatus.CANCELLED]: "text-muted-foreground",
};

/** Agent payouts (§15.1): request a withdrawal to a stored or one-time bank account, and
 * see withdrawal history. Uses a saved beneficiary or a one-time entry. */
export default function AgentPayouts() {
  return (
    <div className="mx-auto max-w-3xl space-y-6 p-4 sm:p-6">
      <header>
        <h1 className="text-lg font-semibold">Withdrawals</h1>
        <p className="text-sm text-muted-foreground">Withdraw your available balance. Payouts are processed within 2 business days.</p>
      </header>
      <RequestWithdrawal />
      <BankAccounts />
      <PayoutHistory />
    </div>
  );
}

function RequestWithdrawal() {
  const banks = useBankAccountsQuery();
  const request = useRequestPayoutMutation();
  const [amount, setAmount] = useState("");
  const [bankAccountId, setBankAccountId] = useState("");

  const submit = () => {
    const naira = Number(amount);
    if (!naira || naira <= 0) {
      toast.error("Enter a valid amount.");
      return;
    }
    if (!bankAccountId) {
      toast.error("Select a bank account.");
      return;
    }
    request.mutate(
      { amountMinor: Math.round(naira * 100), bankAccountId },
      {
        onSuccess: () => {
          toast.success("Withdrawal requested.");
          setAmount("");
        },
        onError: (e: unknown) => toast.error((e as Error)?.message ?? "Could not request the withdrawal."),
      },
    );
  };

  return (
    <Card className="space-y-3 p-4">
      <h2 className="text-sm font-semibold">Request a withdrawal</h2>
      <div className="space-y-2">
        <Label htmlFor="payout-amount">Amount (₦)</Label>
        <Input id="payout-amount" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)}
          placeholder="0.00" data-testid="payout-amount" />
      </div>
      <div className="space-y-2">
        <Label htmlFor="payout-bank">Bank account</Label>
        <select id="payout-bank" value={bankAccountId} onChange={(e) => setBankAccountId(e.target.value)}
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
      <Button onClick={submit} disabled={request.isPending} data-testid="payout-submit">
        Request withdrawal
      </Button>
    </Card>
  );
}

function BankAccounts() {
  const banks = useBankAccountsQuery();
  const add = useAddBankAccountMutation();
  const remove = useRemoveBankAccountMutation();
  const [form, setForm] = useState({ bankName: "", accountNumber: "", accountName: "" });

  const addAccount = () => {
    if (!form.bankName || !form.accountNumber || !form.accountName) {
      toast.error("Fill in all bank details.");
      return;
    }
    add.mutate(form, {
      onSuccess: () => {
        toast.success("Bank account saved.");
        setForm({ bankName: "", accountNumber: "", accountName: "" });
      },
      onError: () => toast.error("Could not save the account."),
    });
  };

  return (
    <Card className="space-y-3 p-4">
      <h2 className="text-sm font-semibold">Bank accounts</h2>
      <AsyncStateComponent<BankAccount[]>
        isLoading={banks.isLoading}
        isError={banks.isError}
        data={banks.data}
        loadingText="Loading accounts…"
        emptyText="No saved accounts."
      >
        {(accounts) =>
          accounts.length === 0 ? (
            <p className="text-sm text-muted-foreground">No saved accounts yet.</p>
          ) : (
            <ul className="divide-y rounded-lg border" data-testid="bank-accounts">
              {accounts.map((a) => (
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

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        <Input placeholder="Bank name" value={form.bankName} onChange={(e) => setForm({ ...form, bankName: e.target.value })}
          data-testid="bank-name" />
        <Input placeholder="Account number" value={form.accountNumber}
          onChange={(e) => setForm({ ...form, accountNumber: e.target.value })} data-testid="bank-number" />
        <Input placeholder="Account name" value={form.accountName}
          onChange={(e) => setForm({ ...form, accountName: e.target.value })} data-testid="bank-account-name" />
      </div>
      <Button variant="outline" size="sm" onClick={addAccount} disabled={add.isPending} data-testid="bank-add">
        Add account
      </Button>
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
                  <li key={p.id} className="flex items-center justify-between gap-3 p-3 text-sm">
                    <div className="min-w-0">
                      <p className="font-semibold tabular-nums">{formatMinor(p.amountMinor, p.currency)}</p>
                      <p className="text-xs text-muted-foreground">{p.bankName} · {p.accountNumber}</p>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className={`text-xs font-medium ${STATUS_TONE[p.status]}`}>{p.status}</span>
                      {p.status === PayoutStatus.REQUESTED && (
                        <Button variant="ghost" size="sm" onClick={() => cancel.mutate(p.id)}>Cancel</Button>
                      )}
                    </div>
                  </li>
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
