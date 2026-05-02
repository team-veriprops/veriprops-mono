"use client";

import { useState } from "react";
import { Button } from "@3rdparty/ui/button";
import { Input } from "@3rdparty/ui/input";
import {
  CreditCard,
  Banknote,
  Globe,
  Copy,
  AlertCircle,
} from "lucide-react";
import { useInitiatePaymentMutation, paymentService } from "../libs/useVerificationQueries";
import type { PaymentMethod, InitiatePaymentResult } from "../libs/payment-service";
import type { Verification } from "../libs/verification-service";
import { getErrorMessage } from "@lib/utils";

interface Props {
  verification: Verification;
  onPaid: (paymentId: string) => void;
}

const METHODS: { value: PaymentMethod; label: string; blurb: string; icon: typeof CreditCard }[] = [
  { value: "CARD", label: "Card", blurb: "Visa / Mastercard / Verve via Flutterwave.", icon: CreditCard },
  { value: "BANK_TRANSFER", label: "Bank transfer", blurb: "Virtual account in NGN, 24-hr expiry.", icon: Banknote },
  { value: "WIRE", label: "International wire", blurb: "USD/GBP/EUR with proof upload.", icon: Globe },
];

export default function PaymentStep({ verification, onPaid }: Props) {
  const [method, setMethod] = useState<PaymentMethod>("CARD");
  const [result, setResult] = useState<InitiatePaymentResult | null>(null);
  const [proofUrl, setProofUrl] = useState("");
  const [proofSaving, setProofSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const initiate = useInitiatePaymentMutation();

  const handleInitiate = async () => {
    setError(null);
    try {
      const res = await initiate.mutateAsync({
        verificationId: verification.id,
        method,
        redirectUrl: `${window.location.origin}/portal/verifications/${verification.id}/confirmed`,
      });
      setResult(res.data ?? null);
      if (res.data?.checkoutUrl && method === "CARD") {
        window.location.href = res.data.checkoutUrl;
      }
    } catch (e) {
      setError(getErrorMessage(e));
    }
  };

  const handleProofUpload = async () => {
    if (!result?.payment?.id) return;
    setProofSaving(true);
    setError(null);
    try {
      await paymentService.uploadWireProof(result.payment.id, { proofUrl });
      onPaid(result.payment.id);
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setProofSaving(false);
    }
  };

  const total = verification.pricing
    ? `${currencySymbol(verification.pricing.currency)}${(
        verification.pricing.totalAmountMinor / 100
      ).toLocaleString()}`
    : "—";

  return (
    <div className="space-y-6">
      <div>
        <h2
          className="text-2xl font-semibold tracking-tight"
          style={{ color: "var(--brand-navy)", fontFamily: "var(--font-display, Manrope)" }}
        >
          Pay for your verification
        </h2>
        <p className="text-sm mt-1" style={{ color: "var(--brand-on-surface-variant)" }}>
          {verification.vid} · {verification.tier} · <span className="font-semibold">{total}</span>
        </p>
      </div>

      {!result ? (
        <>
          <div className="grid sm:grid-cols-3 gap-3">
            {METHODS.map((m) => {
              const isOn = method === m.value;
              const Icon = m.icon;
              return (
                <button
                  key={m.value}
                  type="button"
                  onClick={() => setMethod(m.value)}
                  className="text-left rounded-xl p-4 transition-all"
                  style={{
                    backgroundColor: isOn
                      ? "var(--brand-viridian-xlight)"
                      : "var(--brand-surface-card)",
                    boxShadow: isOn
                      ? "0 0 0 2px var(--brand-viridian), 0px 12px 24px rgba(0,13,34,0.06)"
                      : "0px 12px 24px rgba(0,13,34,0.04)",
                  }}
                >
                  <span
                    className="w-9 h-9 rounded-lg flex items-center justify-center mb-3"
                    style={{
                      backgroundColor: isOn ? "var(--brand-viridian)" : "var(--brand-surface-low)",
                      color: isOn ? "white" : "var(--brand-navy)",
                    }}
                  >
                    <Icon className="w-4 h-4" />
                  </span>
                  <div className="font-semibold text-sm" style={{ color: "var(--brand-navy)" }}>
                    {m.label}
                  </div>
                  <div className="text-xs mt-1" style={{ color: "var(--brand-on-surface-variant)" }}>
                    {m.blurb}
                  </div>
                </button>
              );
            })}
          </div>
          <div className="flex justify-end">
            <Button type="button" disabled={initiate.isPending} onClick={handleInitiate}>
              {initiate.isPending ? "Preparing…" : "Continue"}
            </Button>
          </div>
        </>
      ) : method === "BANK_TRANSFER" && result.instructions ? (
        <Instructions
          title="Bank transfer instructions"
          rows={[
            ["Bank", String(result.instructions.virtualAccountBank ?? "")],
            ["Account number", String(result.instructions.virtualAccountNumber ?? "")],
            [
              "Expires",
              result.instructions.expiresAt
                ? new Date(String(result.instructions.expiresAt)).toLocaleString()
                : "",
            ],
          ]}
          footer="We confirm receipt automatically. Status updates appear on this page."
          onDone={() => onPaid(result.payment.id)}
          doneLabel="I've paid — track my verification"
        />
      ) : method === "WIRE" && result.instructions ? (
        <div className="space-y-4">
          <Instructions
            title="International wire details"
            rows={[
              ["Beneficiary bank", String(result.instructions.beneficiaryBank ?? "")],
              ["SWIFT", String(result.instructions.swift ?? "")],
              ["IBAN", String(result.instructions.iban ?? "")],
              ["Beneficiary", String(result.instructions.beneficiary ?? "")],
              ["Reference", String(result.instructions.reference ?? "")],
            ]}
          />
          <div className="space-y-2">
            <label className="text-xs font-medium" style={{ color: "var(--brand-on-surface-variant)" }}>
              Upload your proof of payment URL
            </label>
            <Input
              placeholder="https://…"
              value={proofUrl}
              onChange={(e) => setProofUrl(e.target.value)}
            />
            <Button
              type="button"
              onClick={handleProofUpload}
              disabled={!proofUrl || proofSaving}
            >
              {proofSaving ? "Uploading…" : "Submit proof"}
            </Button>
          </div>
        </div>
      ) : (
        <div
          className="text-sm rounded-md p-4"
          style={{
            backgroundColor: "var(--brand-surface-low)",
            color: "var(--brand-navy)",
          }}
        >
          Redirecting to checkout…
        </div>
      )}

      {error && (
        <div
          className="flex items-start gap-2 text-sm rounded-md p-3"
          style={{
            color: "var(--destructive)",
            backgroundColor: "rgba(186,26,26,0.06)",
          }}
        >
          <AlertCircle className="w-4 h-4 mt-0.5" />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
}

function Instructions({
  title,
  rows,
  footer,
  onDone,
  doneLabel,
}: {
  title: string;
  rows: [string, string][];
  footer?: string;
  onDone?: () => void;
  doneLabel?: string;
}) {
  return (
    <div
      className="rounded-xl p-5 space-y-3"
      style={{
        backgroundColor: "var(--brand-surface-card)",
        boxShadow: "0px 12px 24px rgba(0,13,34,0.06)",
      }}
    >
      <div className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--brand-viridian)" }}>
        {title}
      </div>
      {rows.map(([label, value]) => (
        <div key={label} className="flex justify-between gap-3 text-sm">
          <span style={{ color: "var(--brand-on-surface-variant)" }}>{label}</span>
          <span className="font-mono text-right" style={{ color: "var(--brand-navy)" }}>
            {value}
            {value && (
              <button
                type="button"
                aria-label={`Copy ${label}`}
                onClick={() => navigator.clipboard.writeText(value)}
                className="ml-2 inline-flex"
              >
                <Copy className="w-3 h-3 inline" />
              </button>
            )}
          </span>
        </div>
      ))}
      {footer && (
        <div className="text-xs pt-2 border-t" style={{ color: "var(--brand-on-surface-variant)", borderColor: "var(--brand-surface-low)" }}>
          {footer}
        </div>
      )}
      {onDone && (
        <Button type="button" onClick={onDone} className="w-full mt-2">
          {doneLabel ?? "Continue"}
        </Button>
      )}
    </div>
  );
}

function currencySymbol(c: string): string {
  const m: Record<string, string> = { NGN: "₦", USD: "$", GBP: "£", EUR: "€" };
  return m[c] ?? "";
}
