"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@3rdparty/ui/dialog";
import { Button } from "@3rdparty/ui/button";
import { payoutService, BankAccount, CreateBankAccountDto } from "./libs/payout-service";
import { payoutQKey } from "./PayoutHistory";
import { getErrorMessage } from "@lib/utils";

interface Props {
  open: boolean;
  onClose: () => void;
}

type Step = "select-bank" | "add-bank" | "enter-amount" | "confirm" | "done";

export default function WithdrawalModal({ open, onClose }: Props) {
  const qc = useQueryClient();
  const [step, setStep] = useState<Step>("select-bank");
  const [selectedBank, setSelectedBank] = useState<BankAccount | null>(null);
  const [amount, setAmount] = useState("");
  const [error, setError] = useState<string | null>(null);

  const [newBank, setNewBank] = useState<CreateBankAccountDto>({
    bankName: "",
    accountNumber: "",
    accountHolderName: "",
    isDefault: false,
  });

  const bankQKey = ["agent", "bank-accounts"];
  const { data: banksRes } = useQuery({
    queryKey: bankQKey,
    queryFn: () => payoutService.listBankAccounts(),
    enabled: open,
  });
  const banks: BankAccount[] = (banksRes as any)?.data ?? [];

  const addBank = useMutation({
    mutationFn: () => payoutService.addBankAccount(newBank),
    onSuccess: (res: any) => {
      qc.invalidateQueries({ queryKey: bankQKey });
      setSelectedBank(res.data);
      setStep("enter-amount");
      setError(null);
    },
    onError: (e: any) => setError(getErrorMessage(e)),
  });

  const withdraw = useMutation({
    mutationFn: () =>
      payoutService.requestWithdrawal(parseFloat(amount), selectedBank!.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: payoutQKey });
      setStep("done");
      setError(null);
    },
    onError: (e: any) => setError(getErrorMessage(e)),
  });

  const handleClose = () => {
    setStep("select-bank");
    setSelectedBank(null);
    setAmount("");
    setError(null);
    setNewBank({ bankName: "", accountNumber: "", accountHolderName: "", isDefault: false });
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent data-testid="withdrawal-modal">
        <DialogHeader>
          <DialogTitle>Request Withdrawal</DialogTitle>
        </DialogHeader>

        {step === "select-bank" && (
          <div className="space-y-3">
            <p className="text-sm text-gray-600">Select a bank account to receive your funds:</p>
            {banks.length === 0 && (
              <p className="text-xs text-gray-400 italic">No bank accounts saved.</p>
            )}
            {banks.map((b) => (
              <button
                key={b.id}
                type="button"
                onClick={() => { setSelectedBank(b); setStep("enter-amount"); }}
                style={{ cursor: "pointer" }}
                className={`w-full rounded-md border p-3 text-left transition-colors hover:border-indigo-400 ${
                  selectedBank?.id === b.id ? "border-indigo-400 bg-indigo-50" : "border-gray-200"
                }`}
                data-testid="bank-account-option"
              >
                <p className="text-sm font-medium text-gray-900">{b.bankName}</p>
                <p className="text-xs text-gray-500">{b.accountNumber} · {b.accountHolderName}</p>
              </button>
            ))}
            <button
              type="button"
              onClick={() => setStep("add-bank")}
              style={{ cursor: "pointer" }}
              className="w-full rounded-md border-2 border-dashed border-gray-300 py-3 text-xs text-gray-500 hover:border-indigo-300 hover:text-indigo-600"
              data-testid="add-bank-account-button"
            >
              + Add new bank account
            </button>
            {error && <p className="text-sm text-red-600">{error}</p>}
          </div>
        )}

        {step === "add-bank" && (
          <div className="space-y-3">
            {["bankName", "accountNumber", "accountHolderName"].map((field) => (
              <div key={field}>
                <label className="block text-xs font-medium text-gray-600 mb-1 capitalize">
                  {field.replace(/([A-Z])/g, " $1").trim()}
                </label>
                <input
                  type="text"
                  value={(newBank as any)[field]}
                  onChange={(e) => setNewBank((b) => ({ ...b, [field]: e.target.value }))}
                  className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  data-testid={`new-bank-${field}`}
                />
              </div>
            ))}
            {error && <p className="text-sm text-red-600">{error}</p>}
          </div>
        )}

        {step === "enter-amount" && selectedBank && (
          <div className="space-y-4">
            <div className="rounded-md bg-gray-50 border border-gray-200 p-3">
              <p className="text-xs text-gray-500">Paying to</p>
              <p className="text-sm font-medium text-gray-900">{selectedBank.bankName}</p>
              <p className="text-xs text-gray-600">{selectedBank.accountNumber} · {selectedBank.accountHolderName}</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Amount (₦)</label>
              <input
                type="number"
                min="1"
                step="0.01"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="0.00"
                className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                data-testid="withdrawal-amount-input"
              />
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
          </div>
        )}

        {step === "confirm" && (
          <div className="space-y-3 py-2">
            <p className="text-sm text-gray-700">
              You are requesting a withdrawal of{" "}
              <span className="font-bold text-gray-900">₦{parseFloat(amount).toLocaleString()}</span>{" "}
              to {selectedBank?.bankName} ({selectedBank?.accountNumber}).
            </p>
            <p className="text-xs text-gray-500">
              Payouts are processed within 2 business days after approval.
            </p>
            {error && <p className="text-sm text-red-600">{error}</p>}
          </div>
        )}

        {step === "done" && (
          <div className="py-4 text-center">
            <p className="text-green-700 font-medium">Withdrawal request submitted.</p>
            <p className="text-sm text-gray-500 mt-1">
              Your request will be reviewed by the finance team.
            </p>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" style={{ cursor: "pointer" }} onClick={handleClose}>
            {step === "done" ? "Close" : "Cancel"}
          </Button>
          {step === "add-bank" && (
            <Button
              style={{ cursor: "pointer" }}
              disabled={addBank.isPending || !newBank.bankName || !newBank.accountNumber}
              onClick={() => addBank.mutate()}
              data-testid="save-bank-account-button"
            >
              {addBank.isPending ? "Saving…" : "Save Account"}
            </Button>
          )}
          {step === "enter-amount" && (
            <Button
              style={{ cursor: "pointer" }}
              disabled={!amount || parseFloat(amount) <= 0}
              onClick={() => setStep("confirm")}
              data-testid="withdrawal-continue-button"
            >
              Continue
            </Button>
          )}
          {step === "confirm" && (
            <Button
              style={{ cursor: "pointer" }}
              disabled={withdraw.isPending}
              onClick={() => withdraw.mutate()}
              data-testid="withdrawal-submit-button"
            >
              {withdraw.isPending ? "Submitting…" : "Confirm Withdrawal"}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
