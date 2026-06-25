import type { Metadata } from "next";
import LandingNav from "@components/website/LandingNav";
import AboutContent from "@components/website/AboutContent";
import CTASection from "@components/website/CTASection";
import LandingFooter from "@components/website/LandingFooter";

export const metadata: Metadata = {
  title: "About Veriprops — Verify Before You Pay",
  description:
    "Why Veriprops exists: we put qualified people on the ground — surveyors, registry agents, lawyers — so Nigerians at home and abroad can buy property with certainty, not blind trust.",
};

export default function AboutPage() {
  return (
    <div className="min-h-screen bg-background">
      <LandingNav />
      <main>
        <AboutContent />
        <CTASection />
      </main>
      <LandingFooter />
    </div>
  );
}
