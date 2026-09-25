"use client";

import { useState } from "react";
import { Button } from "@3rdparty/ui/button";
import ConsentCheckbox from "../ConsentCheckbox";
import {
  consentsFor,
  signupConsentDocuments,
  SIGNUP_CONSENT_TYPES,
} from "@components/website/auth/libs/auth/consent";
import { useConsentDocumentsQuery } from "@components/website/auth/libs/useAuthQueries";
import { ConsentDocumentType, UserConsent } from "@components/website/auth/models";

/**
 * The anchors automation drives. They are part of the auth contract and outlive any change to
 * how the documents are sourced, so they are stated rather than derived from the type.
 */
const TEST_ID_BY_TYPE: Partial<Record<ConsentDocumentType, string>> = {
  [ConsentDocumentType.PLATFORM_TERMS]: "signup-consent-terms",
  [ConsentDocumentType.PRIVACY_POLICY]: "signup-consent-privacy",
};

interface Props {
  loading?: boolean;
  errorMessage?: string | null;
  onSubmit: (consents: UserConsent[]) => void;
  onBack: () => void;
}

export default function ConsentStep({ loading, errorMessage, onSubmit, onBack }: Props) {
  // The versions are the backend's to publish; accepting one this page never showed is what put
  // every new account behind the re-acceptance modal.
  const { data: published = [], isLoading: loadingDocuments } = useConsentDocumentsQuery();
  const documents = signupConsentDocuments(published);
  const ready = documents.length === SIGNUP_CONSENT_TYPES.length;

  const [accepted, setAccepted] = useState<Record<string, boolean>>({});
  const [touched, setTouched] = useState(false);

  const allAccepted = ready && documents.every((doc) => accepted[doc.type]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setTouched(true);
    if (!allAccepted) return;
    onSubmit(consentsFor(documents, new Date().toISOString()));
  };

  return (
    <form className="space-y-6" onSubmit={handleSubmit} noValidate data-testid="signup-consent-form">
      <p className="text-sm leading-relaxed text-brand-on-surface-variant">
        We need your explicit acceptance of the documents below before creating your account. We
        record the exact version you accept along with the timestamp.
      </p>

      <div className="space-y-4">
        {documents.map((doc) => (
          <ConsentCheckbox
            key={doc.type}
            doc={doc}
            checked={!!accepted[doc.type]}
            onChange={(checked) => setAccepted((prev) => ({ ...prev, [doc.type]: checked }))}
            error={touched && !accepted[doc.type] ? "Required to continue" : undefined}
            data-testid={TEST_ID_BY_TYPE[doc.type]}
          />
        ))}
        {loadingDocuments && !ready && (
          <p className="text-sm text-brand-on-surface-variant" data-testid="signup-consent-loading">
            Loading the current terms…
          </p>
        )}
      </div>

      {errorMessage && (
        <div
          className="p-3 rounded-lg text-sm bg-danger/6 text-danger border border-danger/18"
          data-testid="signup-consent-error"
        >
          {errorMessage}
        </div>
      )}

      <div className="flex gap-3 pt-2">
        <Button
          type="button"
          variant="outline"
          className="flex-1"
          onClick={onBack}
          size="lg"
          disabled={loading}
          data-testid="signup-consent-back"
        >
          Back
        </Button>
        <Button
          type="submit"
          className="flex-1"
          size="lg"
          disabled={loading || !ready}
          data-testid="signup-consent-submit"
        >
          {loading ? "Creating account…" : "Create my account"}
        </Button>
      </div>
    </form>
  );
}
