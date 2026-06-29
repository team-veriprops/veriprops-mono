import type { Metadata } from "next";

import LandingNav from "@components/website/LandingNav";
import LandingFooter from "@components/website/LandingFooter";
import SampleReportContent from "@components/website/SampleReportContent";
import { ROUTES } from "@lib/routes";
import { buildMetadata } from "@lib/seo";

export const metadata: Metadata = buildMetadata({
  title: "Sample Certified Report",
  description:
    "See exactly what a Veriprops certified report looks like — Trust Score, Verification ID, registry, physical, boundary, and legal findings, with a legal footer on every page.",
  path: ROUTES.SAMPLE_REPORT,
});

export default function SampleReportPage() {
  return (
    <div className="min-h-screen bg-background">
      <LandingNav />
      <main>
        <SampleReportContent />
      </main>
      <LandingFooter />
    </div>
  );
}
