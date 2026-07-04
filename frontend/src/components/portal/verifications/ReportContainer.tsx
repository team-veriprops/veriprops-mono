"use client";

import { BadgeCheck, Download, HelpCircle, RefreshCw } from "lucide-react";
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
import { CustomerReport } from "@/types/report";
import { cn } from "@lib/utils";

// §3.5 legal footer — shown on every report page and PDF page (parity, §10.2).
const LEGAL_FOOTER =
  "This report represents a professional opinion, not a legal guarantee. Findings are based on " +
  "information available at the time of verification. Veriprops — Jurisdiction: Nigeria. " +
  '"We reduce uncertainty. We do not eliminate it."';

const BAND_CLASS: Record<string, string> = {
  Safe: "text-emerald-600",
  Caution: "text-amber-600",
  "High Risk": "text-red-600",
};

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
              <Verdict report={report} />
              <TrustScore report={report} />

              <div className="mt-4 space-y-2">
                {report.sections
                  .filter((s) => !s.isLegalOpinion || legalOpinionEnabled)
                  .map((s) => (
                    <details key={s.key} className="rounded-lg border p-3" open={s.key === "executive_summary"}>
                      <summary className="cursor-pointer text-sm font-semibold">{s.title}</summary>
                      <p className="mt-2 whitespace-pre-line text-sm text-muted-foreground">{s.body}</p>
                    </details>
                  ))}
              </div>

              <p className="mt-6 border-t pt-3 text-[11px] leading-relaxed text-muted-foreground">
                {LEGAL_FOOTER}
              </p>
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
        <Button size="sm" variant="outline" disabled title="Available soon">
          <RefreshCw className="size-4" /> Request Re-check
        </Button>
      </div>
    </div>
  );
}

function Verdict({ report }: { report: CustomerReport }) {
  return (
    <Card className="mt-4">
      <CardContent className="pt-6">
        <p className="text-base leading-relaxed">{report.verdict}</p>
      </CardContent>
    </Card>
  );
}

function TrustScore({ report }: { report: CustomerReport }) {
  const band = report.trustBand ?? "";
  return (
    <div className="mt-4 flex items-center gap-4 rounded-lg border p-4">
      <div className="text-center">
        <div className={cn("text-3xl font-bold", BAND_CLASS[band])}>{report.trustScore ?? "—"}</div>
        <div className="text-[10px] uppercase text-muted-foreground">/ 100</div>
      </div>
      <div className="min-w-0">
        <div className={cn("flex items-center gap-1 font-semibold", BAND_CLASS[band])}>
          {band}
          <span title="90+ Safe · 60–89 Caution · 0–59 High Risk">
            <HelpCircle className="size-3.5 text-muted-foreground" />
          </span>
        </div>
        <p className="text-sm text-muted-foreground">{report.trustMeaning}</p>
      </div>
    </div>
  );
}
