import { AuthIntent } from "./auth/models";
import { ROUTES, buildAuthUrl } from "@lib/routes";

export interface PricingTier {
  name: string;
  priceNGN: number;
  priceDisplay: string;
  sla: string;
  description: string;
  features: string[];
  popular?: boolean;
  cta: string;
  ctaStyle: "default" | "gradient" | "outline-gold";
}

export interface MethodologyStep {
  step: number;
  title: string;
  description: string;
  icon: string;
}

export interface EcosystemFeature {
  title: string;
  description: string;
  icon: string;
}

export interface AgentType {
  name: string;
  description: string;
  icon: string;
  responsibilities: string[];
}

export interface Testimonial {
  name: string;
  location: string;
  quote: string;
  tier: string;
  initials: string;
}

export interface NavLink {
  label: string;
  href: string;
}

export interface FooterLink {
  label: string;
  href: string;
}

export const navLinks: NavLink[] = [
  { label: "How It Works", href: "#how-it-works" },
  { label: "Pricing", href: "#pricing" },
  { label: "Agents", href: "#agents" },
  { label: "Resources", href: "#resources" },
];

export const ecosystemFeatures: EcosystemFeature[] = [
  {
    title: "Trust Score",
    description:
      "A single, honest number from 0–100, weighted from registry records, encumbrances, and a physical inspection. 90+ is safe, 60–89 means proceed with caution, below 60 is high risk. No jargon; just where you stand.",
    icon: "BarChart3",
  },
  {
    title: "Verification ID",
    description:
      "A unique public reference (VP-YYYY-XXXXXX) for every property we check. Share it with family or your bank — anyone can cross-reference the findings, on this website, without exposing your private details.",
    icon: "Fingerprint",
  },
  {
    title: "Certified Report",
    description:
      "A signed document from the legal and field experts who did the work. Structured, versioned, downloadable as PDF, and detailed enough to support institutional financing.",
    icon: "ShieldCheck",
  },
];

export const methodologySteps: MethodologyStep[] = [
  {
    step: 1,
    title: "Submit Details",
    description: "Share the property's location, upload any documents, and pick your verification tier.",
    icon: "Upload",
  },
  {
    step: 2,
    title: "Cross-Check Records",
    description: "Certified agents validate ownership against official registry and survey records.",
    icon: "Search",
  },
  {
    step: 3,
    title: "Check Encumbrances",
    description: "We surface liens, caveats, pending litigation, or any outstanding claim.",
    icon: "Shield",
  },
  {
    step: 4,
    title: "Run Risk Analysis",
    description: "Zoning, title history, fraud indicators, and the surrounding context.",
    icon: "Lock",
  },
  {
    step: 5,
    title: "Get Certified Report",
    description: "Receive your Trust Score, Verification ID, and signed certified report.",
    icon: "Award",
  },
];

export const agentTypes: AgentType[] = [
  {
    name: "Field Agent",
    description: "Physical on-site inspection and property condition assessment.",
    icon: "MapPin",
    responsibilities: [
      "Site access & condition check",
      "GPS-stamped photo documentation",
      "Neighbourhood profile",
      "Occupancy & usage status",
    ],
  },
  {
    name: "Surveyor",
    description: "Boundary confirmation and precision land measurement.",
    icon: "Ruler",
    responsibilities: [
      "Boundary survey & confirmation",
      "Coordinate & GPS mapping",
      "Survey plan review",
      "Land size accuracy check",
    ],
  },
  {
    name: "Registry Agent",
    description: "Official document search and registry verification.",
    icon: "FileText",
    responsibilities: [
      "Land registry search",
      "Title document verification",
      "Ownership chain tracing",
      "Document authenticity check",
    ],
  },
  {
    name: "Lawyer",
    description: "Legal opinion, encumbrance check, and risk assessment.",
    icon: "Scale",
    responsibilities: [
      "Legal opinion letter",
      "Encumbrance identification",
      "Fraud & risk assessment",
      "Jurisdiction-specific advice",
    ],
  },
];

export const pricingTiers: PricingTier[] = [
  {
    name: "Basic",
    priceNGN: 150000,
    priceDisplay: "₦150k",
    sla: "3–5 business days",
    description: "Document and registry verification. Ideal for preliminary due diligence.",
    features: [
      "Registry Search",
      "Title Document Verification",
      "Ownership Confirmation",
    ],
    cta: "Select Basic",
    ctaStyle: "default",
  },
  {
    name: "Standard",
    priceNGN: 350000,
    priceDisplay: "₦350k",
    sla: "5–7 business days",
    description: "Full on-the-ground verification. The recommended tier for serious buyers.",
    features: [
      "Everything in Basic",
      "Physical Site Inspection",
      "Boundary & Location Survey",
      "Neighbourhood Profile",
    ],
    popular: true,
    cta: "Start Standard",
    ctaStyle: "gradient",
  },
  {
    name: "Premium",
    priceNGN: 750000,
    priceDisplay: "₦750k",
    sla: "7–10 business days",
    description: "Complete verification with legal opinion. For high-value transactions.",
    features: [
      "Everything in Standard",
      "Legal Opinion Letter",
      "Encumbrances & Fraud Assessment",
      "Risk Analysis & Recommendation",
    ],
    cta: "Go Premium",
    ctaStyle: "outline-gold",
  },
];

export const testimonials: Testimonial[] = [
  {
    name: "Emeka Okafor",
    location: "London, UK",
    quote:
      "I was about to wire £65,000 for a property in Lekki. Veriprops found three competing ownership claims before I paid a penny. This service saved my family's financial future.",
    tier: "Premium",
    initials: "EO",
  },
  {
    name: "Adaeze Williams",
    location: "Houston, TX",
    quote:
      "The Standard report was thorough — GPS-stamped photos, boundary survey, full registry search — all delivered within 6 days. Exactly what I needed from 7,000 miles away.",
    tier: "Standard",
    initials: "AW",
  },
  {
    name: "Chukwudi Nwosu",
    location: "Toronto, Canada",
    quote:
      "The Trust Score concept is genius. I now only consider properties scoring above 80. It has fundamentally changed how I approach Nigerian real estate investment.",
    tier: "Basic",
    initials: "CN",
  },
];

export const footerLinks = {
  platform: [
    { label: "How It Works", href: "#how-it-works" },
    { label: "Trust Score Guide", href: "#ecosystem" },
    { label: "Sample Report", href: "#sample" },
    { label: "Pricing", href: "#pricing" },
  ] as FooterLink[],
  company: [
    { label: "Our Story", href: ROUTES.ABOUT },
    { label: "Certification Standards", href: "#agents" },
    { label: "Become an Agent", href: buildAuthUrl(ROUTES.AUTH.GATE, { intent: AuthIntent.AGENT }) },
    { label: "Contact Support", href: "mailto:support@veriprops.com" },
  ] as FooterLink[],
  legal: [
    { label: "Privacy Policy", href: ROUTES.LEGAL.PRIVACY },
    { label: "Terms of Service", href: ROUTES.LEGAL.TERMS },
    { label: "Disclaimer", href: ROUTES.LEGAL.REPORT_DISCLAIMER },
  ] as FooterLink[],
  socials: [
    { label: "Facebook", href: "#" },
    { label: "Twitter", href: "#" },
    { label: "LinkedIn", href: "#" },
    { label: "Instagram", href: "#" },
    { label: "YouTube", href: "#" },
  ] as FooterLink[],
};

export const fxRates: Record<string, { symbol: string; rate: number }> = {
  NGN: { symbol: "₦", rate: 1 },
  USD: { symbol: "$", rate: 0.00065 },
  GBP: { symbol: "£", rate: 0.00052 },
  EUR: { symbol: "€", rate: 0.00060 },
};

export const currencies = ["NGN", "USD", "GBP", "EUR"] as const;
export type Currency = (typeof currencies)[number];

export function formatPrice(priceNGN: number, currency: Currency): string {
  const { symbol, rate } = fxRates[currency];
  const amount = priceNGN * rate;
  if (currency === "NGN") {
    return `${symbol}${(amount / 1000).toFixed(0)}k`;
  }
  return `${symbol}${amount.toFixed(0).replace(/\B(?=(\d{3})+(?!\d))/g, ",")}`;
}

export const CTA_VERIFY_HREF = buildAuthUrl(ROUTES.AUTH.GATE, { intent: AuthIntent.VERIFY });
export const CTA_AGENT_HREF = buildAuthUrl(ROUTES.AUTH.GATE, { intent: AuthIntent.AGENT });
