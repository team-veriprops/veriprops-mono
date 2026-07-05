import { HelpCircle } from "lucide-react";
import { Card, CardContent } from "@3rdparty/ui/card";
import { CustomerReport } from "@/types/report";
import { cn } from "@lib/utils";

// §3.5 legal footer — shown on every report page and PDF page (parity, §10.2).
export const LEGAL_FOOTER =
  "This report represents a professional opinion, not a legal guarantee. Findings are based on " +
  "information available at the time of verification. Veriprops — Jurisdiction: Nigeria. " +
  '"We reduce uncertainty. We do not eliminate it."';

const BAND_CLASS: Record<string, string> = {
  Safe: "text-emerald-600",
  Caution: "text-amber-600",
  "High Risk": "text-red-600",
};

/**
 * Presentational report body (§10.1) — verdict, trust-score band, tier-dependent
 * sections, and the per-page legal footer. Backend owns the content; this only renders
 * it, so the owner's report page and a named-recipient share view stay in parity.
 */
export function ReportView({
  report,
  legalOpinionEnabled,
}: {
  report: CustomerReport;
  legalOpinionEnabled: boolean;
}) {
  const band = report.trustBand ?? "";
  return (
    <>
      <Card className="mt-4">
        <CardContent className="pt-6">
          <p className="text-base leading-relaxed">{report.verdict}</p>
        </CardContent>
      </Card>

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
    </>
  );
}
