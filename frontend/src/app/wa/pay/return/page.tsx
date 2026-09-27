import type { Metadata } from "next";

import WaPayReturn from "@components/website/handoff/WaPayReturn";
import { buildMetadata } from "@lib/seo";

// Where a WhatsApp handoff's hosted checkout returns the customer (§26.5) — never indexable.
export const metadata: Metadata = buildMetadata({
  title: "Confirming Your Payment",
  description: "Your Veriprops verification payment is being confirmed.",
  noindex: true,
});

export default function WaPayReturnPage() {
  return <WaPayReturn />;
}
