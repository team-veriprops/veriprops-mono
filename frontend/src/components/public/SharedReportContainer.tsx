"use client";

import Link from "next/link";
import { AsyncStateComponent } from "@components/ui/AsyncStateComponent";
import BrandLogo from "@components/ui/BrandLogo";
import { Button } from "@3rdparty/ui/button";
import { Card, CardContent } from "@3rdparty/ui/card";
import {
  useAcknowledgeSharedMutation,
  useSharedReportQuery,
} from "@components/portal/libs/useShareQueries";
import { PublicSummaryCard, PublicStateNotice } from "@components/public/PublicSummaryCard";
import { ReportView } from "@components/portal/verifications/ReportView";
import { PublicLookupState, SharedReport } from "@/types/share";
import { ROUTES } from "@lib/routes";

/**
 * Public tokenised share view (§13.2). A summary link renders the summary; a named
 * recipient acknowledges a one-time disclaimer, then sees the full report. Revoked or
 * expired tokens resolve to a neutral not-found notice.
 */
export function SharedReportContainer({ token }: { token: string }) {
  const { data, isLoading, isError } = useSharedReportQuery(token);
  const acknowledge = useAcknowledgeSharedMutation(token);

  return (
    <main className="min-h-dvh bg-muted/30 px-4 py-10">
      <div className="mx-auto mb-8 flex max-w-3xl items-center justify-between">
        <Link href={ROUTES.HOME} aria-label="Veriprops home">
          <BrandLogo />
        </Link>
        <Link href={ROUTES.HOME} className="text-sm text-muted-foreground hover:text-foreground">
          veriprops.ng
        </Link>
      </div>

      <div className="mx-auto max-w-3xl">
        <AsyncStateComponent<SharedReport>
          isLoading={isLoading}
          isError={isError}
          data={data}
          loadingText="Loading the shared report…"
          emptyText="This shared link is not available."
        >
          {(view) => <SharedView view={view} onAck={() => acknowledge.mutate()} acking={acknowledge.isPending} />}
        </AsyncStateComponent>
      </div>
    </main>
  );
}

function SharedView({
  view,
  onAck,
  acking,
}: {
  view: SharedReport;
  onAck: () => void;
  acking: boolean;
}) {
  if (view.state !== PublicLookupState.SHARED) {
    return (
      <PublicStateNotice
        summary={{
          state: view.state,
          verified: false,
          message:
            view.state === PublicLookupState.NOT_FOUND
              ? "This shared link is no longer available. It may have been revoked or expired."
              : undefined,
        }}
      />
    );
  }

  // Named-recipient full report, before the one-time disclaimer acknowledgement (§13.2).
  if (view.requiresAcknowledgement) {
    return (
      <Card className="mx-auto max-w-lg" data-testid="shared-disclaimer">
        <CardContent className="space-y-4 pt-6 text-sm">
          <h2 className="text-base font-semibold">Before you view this report</h2>
          <p className="text-muted-foreground">
            This report is a professional opinion based on the information available at the time of
            verification. It reduces uncertainty — it does not eliminate it. By continuing you
            acknowledge you understand this.
          </p>
          <Button className="w-full" onClick={onAck} disabled={acking} data-testid="shared-ack">
            {acking ? "One moment…" : "I understand — show the report"}
          </Button>
        </CardContent>
      </Card>
    );
  }

  // Full report (named recipient, acknowledged).
  if (view.report) {
    return (
      <div className="rounded-2xl border bg-card p-4 shadow-sm sm:p-6" data-testid="shared-full-report">
        <ReportView report={view.report} legalOpinionEnabled={view.report.legalOpinionIncluded} />
      </div>
    );
  }

  // Summary link.
  return view.summary ? <PublicSummaryCard summary={view.summary} /> : null;
}
