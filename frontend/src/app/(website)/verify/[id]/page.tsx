export const dynamic = "force-dynamic";

import { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { getPublicSummary } from "@/components/public/libs/public-verification-service";
import VerificationBadge from "@components/public/VerificationBadge";
import PublicSummaryCard from "@components/public/PublicSummaryCard";
import { ROUTES } from "@/lib/routes";

interface Props {
  params: Promise<{ id: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  const summary = await getPublicSummary(id);
  const isPublicCompleted = summary?.status === "COMPLETED" && summary?.sharingMode === "PUBLIC";
  return {
    title: summary ? `Verification ${summary.vid} — Veriprops` : "Verification Not Found",
    robots: isPublicCompleted ? "index,follow" : "noindex,nofollow",
  };
}

export default async function PublicVerifyPage({ params }: Props) {
  const { id } = await params;
  const summary = await getPublicSummary(id);

  if (!summary) notFound();

  return (
    <main className="min-h-screen bg-gray-50 py-12 px-4">
      <div className="mx-auto max-w-2xl space-y-6">
        <div className="text-center space-y-3">
          <VerificationBadge status={summary.status} trustBand={summary.trustBand} />
          <h1 className="text-2xl font-bold text-gray-900">Property Verification</h1>
          <p className="text-sm text-gray-500">
            This is an official Veriprops verification record.
          </p>
        </div>

        {summary.status === "COMPLETED" ? (
          <PublicSummaryCard summary={summary} />
        ) : summary.status === "IN_PROGRESS" ? (
          <div className="rounded-lg border border-blue-200 bg-blue-50 p-6 text-center">
            <p className="text-blue-800 font-medium">This verification is currently in progress.</p>
            <p className="text-blue-600 text-sm mt-1">Please check back once the report is complete.</p>
          </div>
        ) : (
          <div className="rounded-lg border border-orange-200 bg-orange-50 p-6 text-center">
            <p className="text-orange-800 font-medium">This verification is currently under review.</p>
            <p className="text-orange-600 text-sm mt-1">Results will be available once the review is complete.</p>
          </div>
        )}

        <div className="text-center pt-4">
          <Link
            href={ROUTES.PORTAL.VERIFICATIONS_NEW}
            className="inline-flex items-center gap-2 rounded-md bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            data-testid="public-verify-cta"
          >
            Start a verification →
          </Link>
        </div>
      </div>
    </main>
  );
}
