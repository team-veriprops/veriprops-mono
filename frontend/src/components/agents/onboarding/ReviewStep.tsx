"use client";

import { useState } from "react";
import { Button } from "@3rdparty/ui/button";
import { Checkbox } from "@3rdparty/ui/checkbox";
import { AlertCircle } from "lucide-react";
import type { AgentApplication } from "../libs/agent-service";

const AGENT_TERMS_VERSION = "1.0.0";

interface Props {
  application: AgentApplication;
  pending?: boolean;
  onBack: () => void;
  onSubmit: (req: {
    truthfulnessAcknowledged: boolean;
    agentTermsConsentVersion: string;
  }) => void;
}

export default function ReviewStep({ application, pending, onBack, onSubmit }: Props) {
  const [truthful, setTruthful] = useState(false);
  const [agentTerms, setAgentTerms] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = () => {
    setError(null);
    if (!truthful || !agentTerms) {
      setError("Please confirm both checkboxes before submitting.");
      return;
    }
    onSubmit({
      truthfulnessAcknowledged: true,
      agentTermsConsentVersion: AGENT_TERMS_VERSION,
    });
  };

  return (
    <div className="space-y-6">
      <div>
        <h2
          className="text-2xl font-semibold tracking-tight"
          style={{ color: "var(--brand-navy)", fontFamily: "var(--font-display, Manrope)" }}
        >
          Review & submit
        </h2>
        <p className="text-sm mt-1" style={{ color: "var(--brand-on-surface-variant)" }}>
          One last look before our admins review your application.
        </p>
      </div>

      <Card>
        <Row label="Roles">
          {application.types.length ? application.types.join(" · ") : "—"}
        </Row>
        <Row label="KYC method">
          {application.kycMethod === "BVN"
            ? `BVN ••${application.bvnLast4 ?? "----"}`
            : application.kycMethod === "ID_DOC"
            ? `${application.idDocType} + selfie`
            : "Not completed"}
        </Row>
        <Row label="Coverage states">
          {application.coverageStates.length
            ? application.coverageStates.join(", ")
            : "—"}
        </Row>
        {application.surveyorLicenceNo && (
          <Row label="Surveyor licence">{application.surveyorLicenceNo}</Row>
        )}
        {application.nbaLicenceNo && (
          <Row label="NBA licence">{application.nbaLicenceNo}</Row>
        )}
        {application.yearsOfExperience !== null && application.yearsOfExperience !== undefined && (
          <Row label="Experience">{application.yearsOfExperience} years</Row>
        )}
        {application.bio && <Row label="Bio">{application.bio}</Row>}
      </Card>

      <div className="space-y-3">
        <ConsentRow
          checked={truthful}
          onChange={setTruthful}
          label="I confirm that all information provided is accurate and complete to the best of my knowledge."
        />
        <ConsentRow
          checked={agentTerms}
          onChange={setAgentTerms}
          label={
            <>
              I have read and accept the{" "}
              <a
                href="/legal/agent-terms"
                target="_blank"
                rel="noopener"
                className="font-medium"
                style={{ color: "var(--brand-viridian)", textDecoration: "underline" }}
              >
                Agent Terms (v{AGENT_TERMS_VERSION})
              </a>
              .
            </>
          }
        />
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
        <Button type="button" disabled={pending} onClick={submit}>
          {pending ? "Submitting…" : "Submit application"}
        </Button>
      </div>
    </div>
  );
}

function Card({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="rounded-xl p-5 space-y-3"
      style={{
        backgroundColor: "var(--brand-surface-card)",
        boxShadow: "0px 12px 24px rgba(0,13,34,0.04)",
      }}
    >
      {children}
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4 text-sm">
      <span style={{ color: "var(--brand-on-surface-variant)" }}>{label}</span>
      <span className="font-medium text-right" style={{ color: "var(--brand-navy)" }}>
        {children}
      </span>
    </div>
  );
}

function ConsentRow({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: React.ReactNode;
}) {
  return (
    <label
      className="flex items-start gap-3 rounded-md p-3 cursor-pointer"
      style={{ backgroundColor: "var(--brand-surface-low)" }}
    >
      <Checkbox checked={checked} onCheckedChange={(v) => onChange(v === true)} className="mt-0.5" />
      <span className="text-sm" style={{ color: "var(--brand-on-surface)" }}>
        {label}
      </span>
    </label>
  );
}
