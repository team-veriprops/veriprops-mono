"use client";

import Link from "next/link";
import { Checkbox } from "@3rdparty/ui/checkbox";
import { ROUTES } from "@lib/routes";

interface Props {
  accepted: boolean;
  onAcceptedChange: (accepted: boolean) => void;
  termsVersion?: string;
}

// The five §5.3 clauses accepted together as one VERIFICATION_TERMS record.
const CLAUSES = [
  "Verification Disclaimer — findings are a professional opinion, not a guarantee.",
  "Findings & Opinion Acknowledgement.",
  "Jurisdiction & Platform-Only Transactions.",
  "Communication Recording — messages are recorded and fraud-scanned.",
  "Refund & Cancellation Policy — cancellation surcharge and reverse-FX refund note apply.",
];

export default function ConsentStep({ accepted, onAcceptedChange, termsVersion }: Props) {
  return (
    <div className="space-y-6" data-testid="verify-new-consent">
      <ul className="space-y-2 text-sm">
        {CLAUSES.map((c) => (
          <li key={c} className="flex gap-2">
            <span className="text-primary">•</span>
            <span className="text-foreground">{c}</span>
          </li>
        ))}
      </ul>

      <label className="flex items-start gap-3">
        <Checkbox
          checked={accepted}
          onCheckedChange={(c) => onAcceptedChange(c === true)}
          data-testid="verify-new-consent-accept"
        />
        <span className="text-sm text-foreground">
          I accept the{" "}
          <Link href={ROUTES.LEGAL.VERIFICATION_TERMS} target="_blank" className="text-primary underline">
            Verification Terms
          </Link>
          {termsVersion ? ` (v${termsVersion})` : ""}.
        </span>
      </label>
    </div>
  );
}
