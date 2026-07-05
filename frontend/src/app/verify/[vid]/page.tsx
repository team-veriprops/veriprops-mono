import type { Metadata } from "next";
import Link from "next/link";
import { fetchPublicSummary } from "@lib/public-lookup.server";
import { buildMetadata } from "@lib/seo";
import { PublicLookupState } from "@/types/share";
import { PublicSummaryCard } from "@components/public/PublicSummaryCard";
import BrandLogo from "@components/ui/BrandLogo";
import { ROUTES } from "@lib/routes";

// Public VID lookup (§13.1). Unauthenticated, summary only. `noindex` unless the
// verification is COMPLETED and publicly shared, per PRD §13.1 / frontend/CLAUDE.md SEO.

export async function generateMetadata({
  params,
}: {
  params: Promise<{ vid: string }>;
}): Promise<Metadata> {
  const { vid } = await params;
  const summary = await fetchPublicSummary(vid);
  const indexable = summary?.state === PublicLookupState.SHARED;
  return buildMetadata({
    title: indexable ? `Verified Property ${vid}` : "Property Verification Lookup",
    description: indexable
      ? "A Veriprops-verified property summary — trust band, tier, and location."
      : "Look up a Veriprops property verification by its ID.",
    path: ROUTES.PUBLIC.VERIFY(vid),
    noindex: !indexable,
  });
}

export default async function PublicVerifyPage({
  params,
}: {
  params: Promise<{ vid: string }>;
}) {
  const { vid } = await params;
  const summary = await fetchPublicSummary(vid);

  return (
    <main className="min-h-dvh bg-muted/30 px-4 py-10">
      <div className="mx-auto mb-8 flex max-w-lg items-center justify-between">
        <Link href={ROUTES.HOME} aria-label="Veriprops home">
          <BrandLogo />
        </Link>
        <Link href={ROUTES.HOME} className="text-sm text-muted-foreground hover:text-foreground">
          veriprops.ng
        </Link>
      </div>
      {summary ? (
        <PublicSummaryCard summary={summary} />
      ) : (
        <PublicSummaryCard summary={{ state: PublicLookupState.NOT_FOUND, verified: false }} />
      )}
    </main>
  );
}
