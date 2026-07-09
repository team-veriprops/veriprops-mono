"use client";

import Link from "next/link";
import { Checkbox } from "@3rdparty/ui/checkbox";
import { KycMethod } from "@/types/agent";
import { ROUTES } from "@lib/routes";
import { humanizeEnumLabel } from "@lib/utils";
import { AgentWizardState } from "./types";

const KYC_METHOD_LABELS: Record<KycMethod, string> = {
  [KycMethod.BVN]: "BVN",
  [KycMethod.GOV_ID]: "Government ID",
};

interface Props {
  state: AgentWizardState;
  update: (patch: Partial<AgentWizardState>) => void;
  termsAccepted: boolean;
  onTermsAcceptedChange: (accepted: boolean) => void;
  termsVersion?: string;
}

export default function ReviewStep({
  state,
  update,
  termsAccepted,
  onTermsAcceptedChange,
  termsVersion,
}: Props) {
  return (
    <div className="space-y-6" data-testid="agent-apply-review">
      <dl className="divide-y divide-border rounded-xl border border-border text-sm">
        <SummaryRow label="Roles" value={state.roles.map(humanizeEnumLabel).join(", ") || "—"} />
        <SummaryRow label="Identity" value={KYC_METHOD_LABELS[state.kyc.method]} />
        <SummaryRow
          label="Credentials"
          value={
            state.credentials.length
              ? state.credentials.map((c) => humanizeEnumLabel(c.role)).join(", ")
              : "None required"
          }
        />
        {state.coverage[0]?.state && <SummaryRow label="Coverage" value={state.coverage[0].state} />}
        {state.yearsExperience != null && (
          <SummaryRow label="Experience" value={`${state.yearsExperience} yr${state.yearsExperience === 1 ? "" : "s"}`} />
        )}
      </dl>

      <label className="flex items-start gap-3">
        <Checkbox
          checked={state.truthfulnessConfirmed}
          onCheckedChange={(c) => update({ truthfulnessConfirmed: c === true })}
          data-testid="agent-apply-truthfulness"
        />
        <span className="text-sm text-foreground">
          I confirm the information provided is true and accurate.
        </span>
      </label>

      <label className="flex items-start gap-3">
        <Checkbox
          checked={termsAccepted}
          onCheckedChange={(c) => onTermsAcceptedChange(c === true)}
          data-testid="agent-apply-terms"
        />
        <span className="text-sm text-foreground">
          I accept the{" "}
          <Link href={ROUTES.LEGAL.AGENT_TERMS} target="_blank" className="text-primary underline">
            Agent Terms
          </Link>
          {termsVersion ? ` (v${termsVersion})` : ""}.
        </span>
      </label>
    </div>
  );
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4 px-4 py-3">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-right font-medium text-foreground">{value}</dd>
    </div>
  );
}
