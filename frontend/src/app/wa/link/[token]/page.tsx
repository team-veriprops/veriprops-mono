import type { Metadata } from "next";

import WaLinkLanding from "@components/website/handoff/WaLinkLanding";
import { buildMetadata } from "@lib/seo";

// A single-use linking invitation from a WhatsApp conversation (§26.4.4) — never indexable.
export const metadata: Metadata = buildMetadata({
  title: "Connect Your WhatsApp",
  description: "Connect your WhatsApp number to your Veriprops account.",
  noindex: true,
});

export default async function WaLinkPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  return <WaLinkLanding token={token} />;
}
