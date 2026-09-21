import type { Metadata } from "next";

import WaIntakeLanding from "@components/website/handoff/WaIntakeLanding";
import { buildMetadata } from "@lib/seo";

// A single-use intake handoff from a WhatsApp conversation (§5.1, D69) — never indexable.
export const metadata: Metadata = buildMetadata({
  title: "Continue Your Verification",
  description: "Pick up the verification you started on WhatsApp.",
  noindex: true,
});

export default async function WaIntakePage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  return <WaIntakeLanding token={token} />;
}
