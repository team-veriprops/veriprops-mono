import type { Metadata } from "next";

import WaHandoffLanding from "@components/website/handoff/WaHandoffLanding";
import { HandoffIntent } from "@/types/handoff";
import { buildMetadata } from "@lib/seo";

// A single-use capability link from a WhatsApp conversation (§7.4.2) — never indexable.
export const metadata: Metadata = buildMetadata({
  title: "Open Your Report",
  description: "Read your Veriprops verification report.",
  noindex: true,
});

export default async function WaHandoffPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  return <WaHandoffLanding intent={HandoffIntent.REPORT} token={token} />;
}
