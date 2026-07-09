import { ChevronDown, HelpCircle } from "lucide-react";
import { Card, CardContent } from "@3rdparty/ui/card";
import { CustomerReport } from "@/types/report";
import { cn } from "@lib/utils";

// §3.5 legal footer — shown on every report page and PDF page (parity, §10.2).
export const LEGAL_FOOTER =
  "This report represents a professional opinion, not a legal guarantee. Findings are based on " +
  "information available at the time of verification. Veriprops — Jurisdiction: Nigeria. " +
  '"We reduce uncertainty. We do not eliminate it."';

// Trust-band presentation. `text` colors the label; `stroke` colors the SVG gauge arc;
// `tint` softly fills the score panel. Backend owns the band string — this only styles it.
const BAND_STYLE: Record<string, { text: string; stroke: string; tint: string }> = {
  Safe: { text: "text-emerald-600 dark:text-emerald-400", stroke: "#10b981", tint: "bg-emerald-500/5 border-emerald-500/20" },
  Caution: { text: "text-amber-600 dark:text-amber-400", stroke: "#f59e0b", tint: "bg-amber-500/5 border-amber-500/20" },
  "High Risk": { text: "text-red-600 dark:text-red-400", stroke: "#ef4444", tint: "bg-red-500/5 border-red-500/20" },
};
const NEUTRAL_STYLE = { text: "text-muted-foreground", stroke: "currentColor", tint: "" };

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
  const style = BAND_STYLE[band] ?? NEUTRAL_STYLE;
  return (
    <>
      <Card className="mt-4">
        <CardContent className="pt-6">
          <p className="text-base leading-relaxed">{report.verdict}</p>
        </CardContent>
      </Card>

      {/* Trust score — the headline deliverable, given a bespoke radial gauge. */}
      <div className={cn("mt-4 flex items-center gap-5 rounded-xl border p-5", style.tint)}>
        <TrustScoreGauge score={report.trustScore} stroke={style.stroke} />
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
 */
function TrustScoreGauge({ score, stroke }: { score?: number | null; stroke: string }) {
  const radius = 34;
  const circumference = 2 * Math.PI * radius;
  const pct = score != null ? Math.max(0, Math.min(100, score)) / 100 : 0;
  const dashOffset = circumference * (1 - pct);
  return (
    <div className="relative shrink-0" aria-hidden>
      <svg width="88" height="88" viewBox="0 0 88 88" className="-rotate-90">
        <circle cx="44" cy="44" r={radius} fill="none" strokeWidth="8" className="stroke-muted" />
        <circle
          cx="44"
          cy="44"
          r={radius}
          fill="none"
          strokeWidth="8"
          strokeLinecap="round"
          stroke={stroke}
          strokeDasharray={circumference}
          strokeDashoffset={dashOffset}
          className="transition-[stroke-dashoffset] duration-700"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-bold tabular-nums text-foreground">{score ?? "—"}</span>
        <span className="text-[10px] uppercase text-muted-foreground">/ 100</span>
      </div>
    </div>
  );
}
