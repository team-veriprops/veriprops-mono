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
import { faqs, withLivePrices } from "@components/website/home.data";
import { faqJsonLd, organizationJsonLd, pricingJsonLd, websiteJsonLd } from "@lib/seo";
import { fetchPublicConfig } from "@lib/public-config.server";

// Re-render at least every 5 minutes, independent of the backend fetch: if the backend is
// unreachable when `next build` prerenders this page, the page must still pick up live prices
// later. Keep in step with PUBLIC_CONFIG_REVALIDATE_SECONDS (route segment config must be a
// literal, so it cannot import the constant).
export const revalidate = 300;

export default async function HomePage() {
  // Tier prices are backend-owned. Reading them on the server puts the same figures in the HTML,
  // in the hydrated pricing section, and in the pricing structured data crawlers index.
  const prices = (await fetchPublicConfig())?.pricingTiers ?? [];
  const pricing = pricingJsonLd(withLivePrices(prices));

  return (
    <div className="min-h-screen bg-background">
      <JsonLd
        data={[
          organizationJsonLd(),
          websiteJsonLd(),
          faqJsonLd(faqs),
          ...(pricing ? [pricing] : []),
        ]}
      />
      <LandingNav />
      <main>
        <HeroSection />
        <WhyWeExist />
        <VerificationEcosystem />
        <RigorousMethodology />
        <VerifiedAgents />
        <PricingSection prices={prices} />
        <TestimonialsSection />
        <FaqSection />
        <CTASection />
      </main>
      <LandingFooter />
    </div>
  );
}
