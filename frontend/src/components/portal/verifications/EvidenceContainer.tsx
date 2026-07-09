"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { AsyncStateComponent } from "@components/ui/AsyncStateComponent";
import { ROUTES } from "@lib/routes";
import { useEvidenceQuery } from "@components/portal/libs/useVerificationQueries";
import { Page } from "@/types/models";
import { CustomerEvidence } from "@/types/tracking";
import { EvidenceGallery } from "./EvidenceGallery";

/** Full chronological evidence feed (§9.4). Role-tagged, tamper-evident. */
export default function EvidenceContainer({ verificationId }: { verificationId: string }) {
  const { data, isLoading, isError } = useEvidenceQuery(verificationId);

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 sm:p-6" data-testid="verify-evidence">
      <Link
        href={ROUTES.PORTAL.VERIFICATION_TRACKING(verificationId)}
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> Back to tracking
      </Link>
      <h1 className="text-lg font-semibold">Evidence</h1>

      <AsyncStateComponent<Page<CustomerEvidence>>
        isLoading={isLoading}
        isError={isError}
        data={data}
        emptyText="No evidence has been approved for viewing yet."
      >
        {(page) =>
          page.items.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Evidence appears here as each stage is reviewed and approved.
            </p>
          ) : (
            <EvidenceGallery items={page.items} />
          )
        }
      </AsyncStateComponent>
    </div>
  );
}
