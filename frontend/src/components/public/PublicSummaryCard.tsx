import { BadgeCheck, ShieldQuestion } from "lucide-react";
import Link from "next/link";
import { PublicLookupState, PublicSummary } from "@/types/share";
import { ROUTES, buildAuthUrl } from "@lib/routes";
import { AuthIntent } from "@components/website/auth/models";

const BAND_CLASS: Record<string, string> = {
  Safe: "text-emerald-600",
  Caution: "text-amber-600",
  "High Risk": "text-red-600",
};

/**
 * The unauthenticated proof summary (§13.1). Renders the summary allow-list only —
 * VID, verified badge, trust *band* (never the number), tier, property type, state &
 * LGA, report version + date. Non-shared states render a neutral message.
 */
export function PublicSummaryCard({ summary }: { summary: PublicSummary }) {
  if (summary.state !== PublicLookupState.SHARED) {
    return <PublicStateNotice summary={summary} />;
  }
  const band = summary.trustBand ?? "";
  return (
    <div className="mx-auto max-w-lg rounded-2xl border bg-card p-6 shadow-sm" data-testid="public-summary">
      <div className="flex items-center gap-2">
        <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2.5 py-1 text-sm font-medium text-primary">
          <BadgeCheck className="size-4" /> Verified
        </span>
        {summary.reportVersion != null && (
          <span className="text-xs text-muted-foreground">v{summary.reportVersion}.0</span>
        )}
      </div>

      <dl className="mt-5 grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
        <Field label="Verification ID" value={summary.vid} mono />
        <Field label="Trust band" value={band} className={BAND_CLASS[band]} />
        <Field label="Tier" value={summary.tier} />
        <Field label="Property type" value={summary.propertyType} />
        <Field label="State" value={summary.stateRegion} />
        <Field label="LGA" value={summary.lga} />
        <Field
          label="Report date"
          value={summary.reportDate ? new Date(summary.reportDate).toLocaleDateString() : undefined}
        />
      </dl>

      <p className="mt-5 border-t pt-3 text-[11px] leading-relaxed text-muted-foreground">
        This is a public summary. The full report, including findings and the numeric trust score,
        is available only to the report owner and named recipients.
      </p>

      <Link
        href={buildAuthUrl(ROUTES.AUTH.SIGNUP, { intent: AuthIntent.VERIFY })}
        className="mt-4 inline-flex w-full items-center justify-center rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary/90"
        data-testid="public-start-cta"
      >
        Start a verification →
      </Link>
    </div>
  );
}

function Field({
  label,
  value,
  mono,
  className,
}: {
  label: string;
  value?: string | null;
  mono?: boolean;
  className?: string;
}) {
  if (!value) return null;
  return (
    <div>
      <dt className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className={`font-medium ${mono ? "font-mono text-xs" : ""} ${className ?? ""}`}>{value}</dd>
    </div>
  );
}

export function PublicStateNotice({ summary }: { summary: PublicSummary }) {
  return (
    <div className="mx-auto max-w-lg rounded-2xl border bg-card p-8 text-center shadow-sm" data-testid="public-state-notice">
      <ShieldQuestion className="mx-auto size-10 text-muted-foreground" />
      <p className="mt-4 text-sm text-muted-foreground">
        {summary.message ?? "This verification summary is not available."}
      </p>
      <Link
        href={buildAuthUrl(ROUTES.AUTH.SIGNUP, { intent: AuthIntent.VERIFY })}
        className="mt-5 inline-flex items-center justify-center rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary/90"
        data-testid="public-start-cta"
      >
        Start a verification →
      </Link>
    </div>
  );
}
