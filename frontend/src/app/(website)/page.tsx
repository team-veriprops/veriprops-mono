import LandingNav from "@components/website/LandingNav";
import HeroSection from "@components/website/HeroSection";
import VerificationEcosystem from "@components/website/VerificationEcosystem";
import RigorousMethodology from "@components/website/RigorousMethodology";
import VerifiedAgents from "@components/website/VerifiedAgents";
import PricingSection from "@components/website/PricingSection";
import TestimonialsSection from "@components/website/TestimonialsSection";
import CTASection from "@components/website/CTASection";
import LandingFooter from "@components/website/LandingFooter";

export default function HomePage() {
  return (
    <div className="min-h-screen" style={{ backgroundColor: "#fff" }}>
      <LandingNav />
      <main>
        <HeroSection />
        <VerificationEcosystem />
        <RigorousMethodology />
        <VerifiedAgents />
        <PricingSection />
        <TestimonialsSection />
        <CTASection />
      </main>
      <LandingFooter />
    </div>
  );
}
