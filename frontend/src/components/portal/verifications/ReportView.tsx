import { ChevronDown, HelpCircle } from "lucide-react";
import { Card, CardContent } from "@3rdparty/ui/card";
import { CustomerReport } from "@/types/report";
import { trustBandStyle } from "@lib/trust-band";
import { cn } from "@lib/utils";

// §3.5 legal footer — shown on every report page and PDF page (parity, §10.2).
export const LEGAL_FOOTER =
  "This report represents a professional opinion, not a legal guarantee. Findings are based on " +
  "information available at the time of verification. Veriprops — Jurisdiction: Nigeria. " +
  '"We reduce uncertainty. We do not eliminate it."';

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
  const style = trustBandStyle(report.trustBand);
  return (
    <>
      <Card className="mt-4">
        <CardContent className="pt-6">
          <p className="text-base leading-relaxed">{report.verdict}</p>
        </CardContent>
      </Card>

      {/* Trust score — the headline deliverable, given a bespoke radial gauge. */}
      <div className={cn("mt-4 flex items-center gap-5 rounded-xl border p-5", style.tint)}>
        <TrustScoreGauge score={report.trustScore} band={band} strokeClass={style.stroke} />
        <div className="min-w-0">
          <div className={cn("flex items-center gap-1.5 text-lg font-semibold", style.text)}>
            {band || "Pending"}
            <span title="90+ Safe · 60–89 Caution · 0–59 High Risk" className="cursor-help">
              <HelpCircle className="size-4 text-muted-foreground" />
            </span>
          </div>
          <p className="mt-0.5 text-sm text-muted-foreground">{report.trustMeaning}</p>
        </div>
      </div>

      <div className="mt-4 space-y-2">
        {report.sections
          .filter((s) => !s.isLegalOpinion || legalOpinionEnabled)
          .map((s) => (
            <details
              key={s.key}
              className="group rounded-lg border p-3 transition-colors hover:border-primary/40"
              open={s.key === "executive_summary"}
            >
              <summary className="flex cursor-pointer items-center justify-between gap-2 text-sm font-semibold [&::-webkit-details-marker]:hidden">
                {s.title}
                <ChevronDown className="size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180" />
              </summary>
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

/**
 * Radial trust-score gauge: an SVG ring filled proportionally to score/100 and colored
 * by the band. Pure presentation over the backend-supplied number — no derivation here.
 *
 * The score is drawn, not written in prose, so the gauge carries the one accessible reading
 * of the report's headline number: hiding it outright would leave a screen-reader user with
 * the band and its sentence but never the figure they describe.
 */
function TrustScoreGauge({
  score,
  band,
  strokeClass,
}: {
  score?: number | null;
  band: string;
  strokeClass: string;
}) {
  const radius = 34;
  const circumference = 2 * Math.PI * radius;
  const pct = score != null ? Math.max(0, Math.min(100, score)) / 100 : 0;
  const dashOffset = circumference * (1 - pct);
  const label =
    score != null
      ? `Trust score ${score} out of 100${band ? ` — ${band}` : ""}`
      : "Trust score not yet available";
  return (
    <div
      className="relative shrink-0"
      role="img"
      aria-label={label}
      data-testid="report-trust-score"
    >
      <svg width="88" height="88" viewBox="0 0 88 88" className="-rotate-90">
        <circle cx="44" cy="44" r={radius} fill="none" strokeWidth="8" className="stroke-muted" />
        <circle
          cx="44"
          cy="44"
          r={radius}
          fill="none"
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={dashOffset}
          className={cn("transition-[stroke-dashoffset] duration-700", strokeClass)}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-bold tabular-nums text-foreground">{score ?? "—"}</span>
        <span className="text-[10px] uppercase text-muted-foreground">/ 100</span>
      </div>
    </div>
  );
}
