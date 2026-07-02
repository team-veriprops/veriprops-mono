"use client";

import Link from "next/link";
import { Checkbox } from "@3rdparty/ui/checkbox";
import { ROUTES } from "@lib/routes";
import { AgentWizardState } from "./types";

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
      <div className="rounded-lg border border-border p-4 text-sm">
        <dl className="space-y-2">
          <div className="flex justify-between gap-4">
            <dt className="text-muted-foreground">Roles</dt>
            <dd className="text-right font-medium">{state.roles.join(", ") || "—"}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-muted-foreground">Identity</dt>
            <dd className="text-right font-medium">{state.kyc.method}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-muted-foreground">Credentials</dt>
            <dd className="text-right font-medium">
              {state.credentials.length ? state.credentials.map((c) => c.role).join(", ") : "None"}
            </dd>
          </div>
          {state.coverage[0]?.state && (
            <div className="flex justify-between gap-4">
              <dt className="text-muted-foreground">Coverage</dt>
              <dd className="text-right font-medium">{state.coverage[0].state}</dd>
            </div>
          )}
        </dl>
      </div>

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
