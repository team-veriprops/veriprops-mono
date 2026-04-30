"use client";

import { useState } from "react";
import { Button } from "@3rdparty/ui/button";
import ConsentCheckbox from "../ConsentCheckbox";
import { SIGNUP_CONSENT_DOCUMENTS } from "@components/website/auth/libs/auth/consent";
import { ConsentDocumentType, UserConsent } from "@components/website/auth/models";
interface Props {
  loading?: boolean;
  errorMessage?: string | null;
  onSubmit: (consents: UserConsent[]) => void;
  onBack: () => void;
}

const PLATFORM_TERMS = SIGNUP_CONSENT_DOCUMENTS.find(
  (d) => d.type === ConsentDocumentType.PLATFORM_TERMS,
)!;
const PRIVACY_POLICY = SIGNUP_CONSENT_DOCUMENTS.find(
  (d) => d.type === ConsentDocumentType.PRIVACY_POLICY,
)!;

export default function ConsentStep({ loading, errorMessage, onSubmit, onBack }: Props) {
  const [acceptedTerms, setAcceptedTerms] = useState(false);
  const [acceptedPrivacy, setAcceptedPrivacy] = useState(false);
  const [touched, setTouched] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setTouched(true);
    if (!acceptedTerms || !acceptedPrivacy) return;
    const now = new Date().toISOString();
    const consents: UserConsent[] = [
      {
        documentType: ConsentDocumentType.PLATFORM_TERMS,
        consentVersion: PLATFORM_TERMS.consentVersion,
        acceptedAt: now,
      },
      {
        documentType: ConsentDocumentType.PRIVACY_POLICY,
        consentVersion: PRIVACY_POLICY.consentVersion,
        acceptedAt: now,
      },
    ];
    onSubmit(consents);
  };

  return (
    <form className="space-y-6" onSubmit={handleSubmit} noValidate>
      <p className="text-sm leading-relaxed" style={{ color: "var(--brand-on-surface-variant)" }}>
        We need your explicit acceptance of the documents below before creating your account. We
        record the exact version you accept along with the timestamp.
      </p>

      <div className="space-y-4">
        <ConsentCheckbox
          doc={PLATFORM_TERMS}
          checked={acceptedTerms}
          onChange={setAcceptedTerms}
          error={touched && !acceptedTerms ? "Required to continue" : undefined}
        />
        <ConsentCheckbox
          doc={PRIVACY_POLICY}
          checked={acceptedPrivacy}
          onChange={setAcceptedPrivacy}
          error={touched && !acceptedPrivacy ? "Required to continue" : undefined}
        />
      </div>

      {errorMessage && (
        <div
          className="p-3 rounded-lg text-sm"
          style={{
            backgroundColor: "rgba(186,26,26,0.06)",
            color: "var(--danger)",
            border: "1px solid rgba(186,26,26,0.18)",
          }}
        >
          {errorMessage}
        </div>
      )}

      <div className="flex gap-3 pt-2">
        <Button type="button" variant="outline" className="flex-1" onClick={onBack} size="lg" disabled={loading}>
          Back
        </Button>
        <Button type="submit" className="flex-1" size="lg" disabled={loading}>
          {loading ? "Creating account…" : "Create my account"}
        </Button>
      </div>
    </form>
  );
}
