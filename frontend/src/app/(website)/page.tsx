import LandingNav from "@components/website/LandingNav";
import HeroSection from "@components/website/HeroSection";
import WhyWeExist from "@components/website/WhyWeExist";
import VerificationEcosystem from "@components/website/VerificationEcosystem";
import RigorousMethodology from "@components/website/RigorousMethodology";
import VerifiedAgents from "@components/website/VerifiedAgents";
import PricingSection from "@components/website/PricingSection";
import TestimonialsSection from "@components/website/TestimonialsSection";
import FaqSection from "@components/website/FaqSection";
import CTASection from "@components/website/CTASection";
import LandingFooter from "@components/website/LandingFooter";
import JsonLd from "@components/seo/JsonLd";
import { faqs } from "@components/website/home.data";
import { faqJsonLd, organizationJsonLd, websiteJsonLd } from "@lib/seo";

export default function HomePage() {
  return (
    <div className="min-h-screen bg-background">
      <JsonLd data={[organizationJsonLd(), websiteJsonLd(), faqJsonLd(faqs)]} />
      <LandingNav />
      <main>
        <HeroSection />
        <WhyWeExist />
        <VerificationEcosystem />
        <RigorousMethodology />
        <VerifiedAgents />
        <PricingSection />
        <TestimonialsSection />
        <FaqSection />
        <CTASection />
      </main>
      <LandingFooter />
    </div>
  );
}
