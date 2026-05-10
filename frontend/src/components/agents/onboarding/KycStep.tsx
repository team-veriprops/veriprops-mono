"use client";

import { useState } from "react";
import { Button } from "@3rdparty/ui/button";
import { Input } from "@3rdparty/ui/input";
import { ShieldCheck, FileText, Camera, AlertCircle, Check } from "lucide-react";
import type {
  AgentApplication,
  BvnVerificationResult,
  IdDocType,
  KycMethod,
} from "../libs/agent-service";

interface Props {
  application: AgentApplication;
  onVerifyBvn: (bvn: string) => Promise<BvnVerificationResult | null>;
  onUploadDocs: (payload: {
    idDocType: IdDocType;
    idDocUrl: string;
    selfieUrl: string;
  }) => Promise<void>;
  onContinue: () => void;
  onBack: () => void;
  pending?: boolean;
}

const ID_DOC_OPTIONS: { value: IdDocType; label: string }[] = [
  { value: "NIN", label: "NIN" },
  { value: "PASSPORT", label: "International Passport" },
  { value: "DRIVERS_LICENCE", label: "Driver's Licence" },
  { value: "VOTERS_CARD", label: "Voter's Card" },
];

export default function KycStep({
  application,
  onVerifyBvn,
  onUploadDocs,
  onContinue,
  onBack,
  pending,
}: Props) {
  const initial: KycMethod = application.kycMethod ?? "BVN";
  const [method, setMethod] = useState<KycMethod>(initial);
  const [bvn, setBvn] = useState<string>("");
  const [bvnError, setBvnError] = useState<string | null>(null);
  const [bvnVerifying, setBvnVerifying] = useState(false);

  const [idDocType, setIdDocType] = useState<IdDocType>(
    application.idDocType ?? "NIN",
  );
  const [idDocUrl, setIdDocUrl] = useState<string>(application.idDocUploaded ? "uploaded" : "");
  const [selfieUrl, setSelfieUrl] = useState<string>(
    application.selfieUploaded ? "uploaded" : "",
  );
  const [docsError, setDocsError] = useState<string | null>(null);

  const bvnDone = !!application.bvnVerifiedAt && !!application.bvnLast4;
  const docsDone = application.idDocUploaded && application.selfieUploaded;
  const canContinue = (method === "BVN" && bvnDone) || (method === "ID_DOC" && docsDone);

  const handleVerify = async () => {
    setBvnError(null);
    setBvnVerifying(true);
    try {
      const result = await onVerifyBvn(bvn);
      if (result && !result.verified) {
        setBvnError(result.failureReason || "BVN could not be verified");
      }
    } finally {
      setBvnVerifying(false);
    }
  };

  const handleSubmitDocs = async () => {
    setDocsError(null);
    if (!idDocUrl || !selfieUrl) {
      setDocsError("Both ID document and selfie are required");
      return;
    }
    await onUploadDocs({ idDocType, idDocUrl, selfieUrl });
  };

  return (
    <div className="space-y-6">
      <div>
        <h2
          className="text-2xl font-semibold tracking-tight"
          style={{ color: "var(--brand-navy)", fontFamily: "var(--font-display, Manrope)" }}
        >
          Verify your identity
        </h2>
        <p className="text-sm mt-1" style={{ color: "var(--brand-on-surface-variant)" }}>
          Pick BVN for instant verification, or upload an ID with a selfie.
        </p>
      </div>

      <div
        className="grid grid-cols-2 rounded-lg p-1 gap-1"
        style={{ backgroundColor: "var(--brand-surface-low)" }}
      >
        <button
          type="button"
          data-testid="agent-wizard-kyc-method-bvn"
          onClick={() => setMethod("BVN")}
          className="rounded-md py-2 text-sm font-medium transition-colors"
          style={{
            backgroundColor: method === "BVN" ? "white" : "transparent",
            color: method === "BVN" ? "var(--brand-navy)" : "var(--brand-on-surface-variant)",
            boxShadow: method === "BVN" ? "0px 4px 12px rgba(0,13,34,0.06)" : undefined,
          }}
        >
          BVN
        </button>
        <button
          type="button"
          data-testid="agent-wizard-kyc-method-id-doc"
          onClick={() => setMethod("ID_DOC")}
          className="rounded-md py-2 text-sm font-medium transition-colors"
          style={{
            backgroundColor: method === "ID_DOC" ? "white" : "transparent",
            color: method === "ID_DOC" ? "var(--brand-navy)" : "var(--brand-on-surface-variant)",
            boxShadow: method === "ID_DOC" ? "0px 4px 12px rgba(0,13,34,0.06)" : undefined,
          }}
        >
          ID + Selfie
        </button>
      </div>

      {method === "BVN" ? (
        <div className="space-y-3">
          <label className="block">
            <span
              className="text-xs font-medium block mb-1.5"
              style={{ color: "var(--brand-on-surface-variant)" }}
            >
              Bank Verification Number (11 digits)
            </span>
            <Input
              inputMode="numeric"
              maxLength={11}
              placeholder="••••••••••"
              data-testid="agent-wizard-bvn-input"
              value={bvn}
              onChange={(e) => setBvn(e.target.value.replace(/\D/g, ""))}
              disabled={bvnDone}
            />
          </label>
          {bvnDone ? (
            <div
              className="flex items-center gap-2 text-sm rounded-md p-3"
              style={{
                color: "var(--success)",
                backgroundColor: "rgba(58,154,106,0.08)",
              }}
            >
              <Check className="w-4 h-4" strokeWidth={3} />
              <span>
                Verified — last 4 digits: <strong>{application.bvnLast4}</strong>
              </span>
            </div>
          ) : (
            <Button
              type="button"
              data-testid="agent-wizard-bvn-verify"
              onClick={handleVerify}
              disabled={bvn.length !== 11 || bvnVerifying}
              className="w-full"
            >
              <ShieldCheck className="w-4 h-4 mr-2" />
              {bvnVerifying ? "Verifying…" : "Verify BVN"}
            </Button>
          )}
          {bvnError && (
            <div
              className="flex items-start gap-2 text-sm rounded-md p-3"
              style={{
                color: "var(--destructive)",
                backgroundColor: "rgba(186,26,26,0.06)",
              }}
            >
              <AlertCircle className="w-4 h-4 mt-0.5" />
              <span>{bvnError}</span>
            </div>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          <label className="block">
            <span
              className="text-xs font-medium block mb-1.5"
              style={{ color: "var(--brand-on-surface-variant)" }}
            >
              Document type
            </span>
            <select
              value={idDocType}
              data-testid="agent-wizard-id-doc-type"
              onChange={(e) => setIdDocType(e.target.value as IdDocType)}
              className="w-full rounded-md py-2.5 px-3 text-sm"
              style={{
                backgroundColor: "var(--brand-surface-card)",
                color: "var(--brand-navy)",
                border: "1px solid var(--border)",
              }}
            >
              {ID_DOC_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>

          <UrlField
            label="ID document URL (uploaded to our storage)"
            icon={FileText}
            value={idDocUrl}
            onChange={setIdDocUrl}
            done={application.idDocUploaded}
          />

          <UrlField
            label="Selfie URL"
            icon={Camera}
            value={selfieUrl}
            onChange={setSelfieUrl}
            done={application.selfieUploaded}
          />

          {!docsDone && (
            <Button type="button" onClick={handleSubmitDocs} className="w-full" disabled={pending}>
              {pending ? "Saving…" : "Save documents"}
            </Button>
          )}
          {docsError && (
            <div
              className="flex items-start gap-2 text-sm rounded-md p-3"
              style={{
                color: "var(--destructive)",
                backgroundColor: "rgba(186,26,26,0.06)",
              }}
            >
              <AlertCircle className="w-4 h-4 mt-0.5" />
              <span>{docsError}</span>
            </div>
          )}
          {application.selfieMatchScore !== null && (
            <div
              className="text-xs rounded-md p-3"
              style={{
                color: "var(--brand-on-surface-variant)",
                backgroundColor: "var(--brand-surface-low)",
              }}
            >
              Selfie match score: <strong>{application.selfieMatchScore}/100</strong>
            </div>
          )}
        </div>
      )}

      <div className="flex justify-between pt-2">
        <Button type="button" variant="outline" data-testid="agent-wizard-kyc-back" onClick={onBack}>
          Back
        </Button>
        <Button type="button" data-testid="agent-wizard-kyc-continue" disabled={!canContinue || pending} onClick={onContinue}>
          Continue
        </Button>
      </div>
    </div>
  );
}

function UrlField({
  label,
  icon: Icon,
  value,
  onChange,
  done,
}: {
  label: string;
  icon: typeof FileText;
  value: string;
  onChange: (v: string) => void;
  done: boolean;
}) {
  return (
    <label className="block">
      <span
        className="text-xs font-medium block mb-1.5"
        style={{ color: "var(--brand-on-surface-variant)" }}
      >
        {label}
      </span>
      <div className="relative">
        <Icon
          className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2"
          style={{ color: "var(--brand-on-surface-variant)" }}
        />
        <Input
          placeholder="https://…"
          className="pl-9"
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
        {done && (
          <Check
            className="w-4 h-4 absolute right-3 top-1/2 -translate-y-1/2"
            style={{ color: "var(--success)" }}
            strokeWidth={3}
          />
        )}
      </div>
    </label>
  );
}
