import type { Metadata } from "next";
import { SharedReportContainer } from "@components/public/SharedReportContainer";
import { buildMetadata } from "@lib/seo";

// Private tokenised share link (§13.2) — always noindex (it's a bearer capability link).
export const metadata: Metadata = buildMetadata({
  title: "Shared Verification Report",
  description: "A Veriprops property verification report shared with you.",
  noindex: true,
});

export default async function SharedReportPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  return <SharedReportContainer token={token} />;
}
