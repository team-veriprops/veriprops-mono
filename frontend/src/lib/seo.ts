import type { Metadata } from "next";

/**
 * Canonical site identity used by every page's metadata and structured data.
 * Single source of truth so titles, canonicals, and Open Graph stay consistent.
 */
export const SITE = {
  name: "Veriprops",
  url: process.env.NEXT_PUBLIC_SITE_URL ?? "https://veriprops.ng",
  defaultTitle:
    "Veriprops — Verify Property Ownership & Land Size in Nigeria | Stop Scams Before You Pay",
  titleSuffix: "Veriprops",
  description:
    "Independent property verification for Nigerian buyers at home and abroad. We validate ownership, survey plans, land size, encumbrances, and real-world accuracy before you pay.",
  ogImage: "/og-image.png",
  twitter: "@veriprops",
  locale: "en_NG",
} as const;

export interface PageSeo {
  /** Page title (brand suffix is appended automatically). Omit for the site default. */
  title?: string;
  description?: string;
  /** Canonical path, e.g. "/legal/terms". Resolved to an absolute URL via metadataBase. */
  path?: string;
  image?: string;
  type?: "website" | "article";
  /** When true, emit `robots: noindex` (e.g. in-progress VID lookup pages, PRD R1.6). */
  noindex?: boolean;
  keywords?: string[];
}

/** Build the full document title with the brand suffix, avoiding duplication. */
export function pageTitle(title?: string): string {
  if (!title) return SITE.defaultTitle;
  return title.includes(SITE.titleSuffix) ? title : `${title} | ${SITE.titleSuffix}`;
}

/**
 * Shared metadata builder — every public page should produce its `metadata`
 * (or `generateMetadata`) through this so canonical, Open Graph, Twitter, and
 * robots stay uniform. See the standing SEO convention in CLAUDE-adjacent docs.
 */
export function buildMetadata(seo: PageSeo = {}): Metadata {
  const title = pageTitle(seo.title);
  const description = seo.description ?? SITE.description;
  const image = seo.image ?? SITE.ogImage;
  const canonical = seo.path ?? "/";

  return {
    metadataBase: new URL(SITE.url),
    title,
    description,
    keywords: seo.keywords,
    alternates: { canonical },
    robots: seo.noindex ? { index: false, follow: false } : { index: true, follow: true },
    openGraph: {
      title,
      description,
      url: canonical,
      siteName: SITE.name,
      type: seo.type ?? "website",
      locale: SITE.locale,
      images: [{ url: image }],
    },
    twitter: {
      card: "summary_large_image",
      site: SITE.twitter,
      title,
      description,
      images: [{ url: image }],
    },
  };
}

/** Absolute URL for a path, for structured-data `url`/`@id` fields. */
export function absoluteUrl(path = "/"): string {
  return new URL(path, SITE.url).toString();
}

// ─── Structured-data (JSON-LD) builders ─────────────────────────────────────

export function organizationJsonLd() {
  return {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: SITE.name,
    url: SITE.url,
    logo: absoluteUrl(SITE.ogImage),
    description: SITE.description,
    areaServed: "NG",
  };
}

export function websiteJsonLd() {
  return {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: SITE.name,
    url: SITE.url,
  };
}

export function legalDocumentJsonLd(opts: {
  title: string;
  description?: string;
  path: string;
  datePublished?: string;
  version?: string;
}) {
  return {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: opts.title,
    description: opts.description ?? opts.title,
    url: absoluteUrl(opts.path),
    datePublished: opts.datePublished,
    version: opts.version,
    publisher: { "@type": "Organization", name: SITE.name },
  };
}

export function faqJsonLd(faqs: { question: string; answer: string }[]) {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: faqs.map((f) => ({
      "@type": "Question",
      name: f.question,
      acceptedAnswer: { "@type": "Answer", text: f.answer },
    })),
  };
}
