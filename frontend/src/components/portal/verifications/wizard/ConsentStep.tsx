"use client";

import { useState } from "react";
import { Button } from "@3rdparty/ui/button";
import { Checkbox } from "@3rdparty/ui/checkbox";
import { AlertCircle } from "lucide-react";

const CONSENT_VERSION = "1.0.0";

interface ConsentItem {
  type: string;
  title: string;
  body: string;
  href: string;
}

const ITEMS: ConsentItem[] = [
  {
    type: "VERIFICATION_DISCLAIMER",
    title: "Verification Disclaimer",
    body: "I understand the verification report represents Veriprops' professional opinion, not a legal guarantee.",
    href: "/legal/verification-disclaimer",
  },
  {
    type: "FINDINGS_OPINION_ACK",
    title: "Findings & Opinion Acknowledgement",
    body: "I acknowledge that findings are based on information available at the time of verification.",
    href: "/legal/findings-opinion",
  },
  {
    type: "JURISDICTION_PLATFORM_ONLY",
    title: "Jurisdiction & Platform-Only Transactions",
    body: "All payments and communication for this verification will happen on the Veriprops platform.",
    href: "/legal/jurisdiction",
  },
  {
    type: "COMMUNICATION_RECORDING",
    title: "Communication Recording",
    body: "Messages exchanged with Veriprops administrators and on the platform are recorded for audit.",
    href: "/legal/communication-recording",
  },
  {
    type: "REFUND_POLICY",
    title: "Refund & Cancellation Policy",
    body: "I have read and accept the refund and cancellation policy.",
    href: "/legal/refund-policy",
  },
];

interface Props {
  pending?: boolean;
  onBack: () => void;
  onSubmit: (consents: { documentType: string; consentVersion: string }[]) => void;
}

export default function ConsentStep({ pending, onBack, onSubmit }: Props) {
  const [accepted, setAccepted] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);

  const toggle = (type: string) => {
    setAccepted((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  };

  const handleSubmit = () => {
    setError(null);
    if (accepted.size < ITEMS.length) {
      setError("Please accept all five disclosures before proceeding.");
      return;
    }
    onSubmit(
      ITEMS.map((it) => ({
        documentType: it.type,
        consentVersion: CONSENT_VERSION,
      })),
    );
  };

  return (
    <div className="space-y-6">
      <div>
        <h2
          className="text-2xl font-semibold tracking-tight"
          style={{ color: "var(--brand-navy)", fontFamily: "var(--font-display, Manrope)" }}
        >
          Review & accept disclosures
        </h2>
        <p className="text-sm mt-1" style={{ color: "var(--brand-on-surface-variant)" }}>
          Each box must be ticked individually — we record the exact version you saw.
        </p>
      </div>

      <div className="space-y-3">
        {ITEMS.map((it) => {
          const isOn = accepted.has(it.type);
          return (
            <label
              key={it.type}
              className="flex items-start gap-3 rounded-md p-4 cursor-pointer"
              style={{ backgroundColor: "var(--brand-surface-low)" }}
            >
              <Checkbox
                checked={isOn}
                onCheckedChange={() => toggle(it.type)}
                className="mt-1"
              />
              <div className="flex-1 text-sm">
                <div
                  className="font-semibold"
                  style={{ color: "var(--brand-navy)" }}
                >
                  {it.title}
                </div>
                <div
                  className="text-xs mt-1 leading-relaxed"
                  style={{ color: "var(--brand-on-surface-variant)" }}
                >
                  {it.body}
                </div>
                <a
                  href={it.href}
                  target="_blank"
                  rel="noopener"
                  className="text-xs underline mt-1 inline-block"
                  style={{ color: "var(--brand-viridian)" }}
                >
                  Read full text (v{CONSENT_VERSION})
                </a>
              </div>
            </label>
          );
        })}
      </div>

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

      <div className="flex justify-between pt-2">
        <Button type="button" variant="outline" onClick={onBack}>
          Back
        </Button>
        <Button type="button" disabled={pending} onClick={handleSubmit}>
          {pending ? "Submitting…" : "Submit & continue to payment"}
        </Button>
      </div>
    </div>
  );
}
