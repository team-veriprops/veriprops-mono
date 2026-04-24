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
      "Our proprietary weighted algorithm calculates risk from registry records, encumbrances, and ground inspection. 90+ is Safe — 60–89 is Caution — 0–59 is High Risk.",
    icon: "BarChart3",
  },
  {
    title: "Verification ID",
    description:
      "A unique, immutable public identifier (VP-YYYY-XXXXXX) for every verified property. Share it — anyone can cross-reference findings without exposing your private data.",
    icon: "Fingerprint",
  },
  {
    title: "Certified Report",
    description:
      "A comprehensive signed document from legal and site experts. Structured, versioned (v1, v2…), downloadable as PDF, and admissible for institutional financing.",
    icon: "ShieldCheck",
  },
];

export const methodologySteps: MethodologyStep[] = [
  {
    step: 1,
    title: "Submit Details",
    description: "Provide property coordinates, upload documents, and select your verification tier.",
    icon: "Upload",
  },
  {
    step: 2,
    title: "Cross-Check Records",
    description: "We validate ownership against official registry and survey records with certified agents.",
    icon: "Search",
  },
  {
    step: 3,
    title: "Check Encumbrances",
    description: "Identify liens, caveats, pending litigations, or any outstanding claims on the property.",
    icon: "Shield",
  },
  {
    step: 4,
    title: "Run Risk Analysis",
    description: "Assessment of area zoning, title history, fraud indicators, and surrounding property context.",
    icon: "Lock",
  },
  {
    step: 5,
    title: "Get Certified Report",
    description: "Receive your high-authority digital report with Trust Score, Verification ID, and agent sign-offs.",
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
  resources: [
    { label: "Certification Standards", href: "#" },
    { label: "Verification Process", href: "#how-it-works" },
    { label: "Trust Score Guide", href: "#" },
    { label: "Sample Report", href: "#" },
  ] as FooterLink[],
  company: [
    { label: "Privacy Policy", href: "#" },
    { label: "Terms of Service", href: "#" },
    { label: "Contact Support", href: "#" },
    { label: "Become an Agent", href: "/auth?intent=agent" },
  ] as FooterLink[],
  socials: [
    { label: "Twitter", href: "#" },
    { label: "LinkedIn", href: "#" },
    { label: "Instagram", href: "#" },
  ] as FooterLink[],
};

export const fxRates: Record<string, { symbol: string; rate: number }> = {
  NGN: { symbol: "₦", rate: 1 },
  USD: { symbol: "$", rate: 0.00065 },
  GBP: { symbol: "£", rate: 0.00052 },
  EUR: { symbol: "€", rate: 0.00060 },
};
