"use client";

import { useState } from "react";
import { BadgeCheck, Download, RefreshCw, Share2 } from "lucide-react";
import { Button } from "@3rdparty/ui/button";
import { Card, CardContent } from "@3rdparty/ui/card";
import { CopyText } from "@components/ui/CopyText";
import { AsyncStateComponent } from "@components/ui/AsyncStateComponent";
import { usePublicConfigQuery } from "@components/website/auth/libs/useAuthQueries";
import {
  useAcknowledgeReportMutation,
  useReportQuery,
} from "@components/portal/libs/useReportQueries";
import { reportService } from "@components/portal/libs/useReportQueries";
import { ReportShareModal } from "@components/portal/verifications/ReportShareModal";
import { ReportView } from "@components/portal/verifications/ReportView";
import { CustomerReport } from "@/types/report";
import { cn } from "@lib/utils";

export default function ReportContainer({ verificationId }: { verificationId: string }) {
  const { data, isLoading, isError } = useReportQuery(verificationId);
  const { data: config } = usePublicConfigQuery();
  const acknowledge = useAcknowledgeReportMutation();
  const legalOpinionEnabled = !!config?.legalOpinionEnabled;

  return (
    <div className="mx-auto max-w-3xl space-y-5 p-4 sm:p-6" data-testid="verify-report">
      <AsyncStateComponent<CustomerReport>
        isLoading={isLoading}
        isError={isError}
        data={data}
        loadingText="Loading your report…"
        emptyText="Your report is not ready yet."
      >
        {(report) => (
          <>
            {!report.acknowledged && (
              <AccessGate
                onAccept={() => acknowledge.mutate(verificationId)}
                pending={acknowledge.isPending}
              />
            )}

            <div className={cn(!report.acknowledged && "pointer-events-none select-none blur-sm")}>
              {report.superseded && (
                <div className="mb-3 rounded-md border border-amber-300 bg-amber-50 p-2 text-center text-sm text-amber-800">
                  This is a superseded version of the report.
                </div>
              )}

              <Header report={report} verificationId={verificationId} />
              <ReportView report={report} legalOpinionEnabled={legalOpinionEnabled} />
            </div>
          </>
        )}
      </AsyncStateComponent>
    </div>
  );
}

function AccessGate({ onAccept, pending }: { onAccept: () => void; pending: boolean }) {
  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/60 p-4" role="dialog" aria-modal="true">
      <Card className="max-w-md">
        <CardContent className="space-y-4 pt-6 text-sm">
          <h2 className="text-base font-semibold">Before you view your report</h2>
          <p className="text-muted-foreground">
            This report is a professional opinion based on the information available at the time of
            verification. It reduces uncertainty — it does not eliminate it. By continuing you
            acknowledge you understand this.
          </p>
          <Button className="w-full" onClick={onAccept} disabled={pending} data-testid="report-gate-accept">
            {pending ? "One moment…" : "I understand — show my report"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

function Header({ report, verificationId }: { report: CustomerReport; verificationId: string }) {
  const [shareOpen, setShareOpen] = useState(false);
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
          <BadgeCheck className="size-3.5" /> Verified
        </span>
        <span className="text-xs text-muted-foreground">
          v{report.reportVersion}.0
          {report.releasedAt ? ` · ${new Date(report.releasedAt).toLocaleDateString()}` : ""}
          {report.tier ? ` · ${report.tier}` : ""}
        </span>
      </div>
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <span>Verification ID</span>
        <CopyText text={report.vid} />
      </div>
      {report.address && <p className="text-sm font-medium">{report.address}</p>}
      <div className="flex flex-wrap gap-2">
        <Button asChild size="sm">
          {/* server-generated branded PDF */}
          <a href={reportService.pdfUrl(verificationId)} target="_blank" rel="noopener noreferrer" data-testid="report-download-pdf">
            <Download className="size-4" /> Download PDF
          </a>
        </Button>
        <Button size="sm" variant="outline" onClick={() => setShareOpen(true)} data-testid="report-share">
          <Share2 className="size-4" /> Share
        </Button>
        <Button size="sm" variant="outline" disabled title="Available soon">
          <RefreshCw className="size-4" /> Request Re-check
        </Button>
      </div>
      <ReportShareModal
        verificationId={verificationId}
        vid={report.vid}
        open={shareOpen}
        onOpenChange={setShareOpen}
      />
    </div>
  );
}
