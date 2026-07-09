import type { Metadata } from "next";
import { notFound } from "next/navigation";

import LandingNav from "@components/website/LandingNav";
import LandingFooter from "@components/website/LandingFooter";
import LegalDocument from "@components/website/legal/LegalDocument";
import JsonLd from "@components/seo/JsonLd";
import { fetchLegalDocument } from "@lib/legal.server";
import { buildMetadata, legalDocumentJsonLd } from "@lib/seo";

type LegalPageProps = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: LegalPageProps): Promise<Metadata> {
  const { slug } = await params;
  const doc = await fetchLegalDocument(slug);
  if (!doc) return buildMetadata({ title: "Legal", noindex: true });
  return buildMetadata({
    title: doc.title,
    description: `${doc.title} — Veriprops. Version ${doc.consentVersion}.`,
    path: doc.href,
    type: "article",
  });
}

export default async function LegalDocumentPage({ params }: LegalPageProps) {
  const { slug } = await params;
  const doc = await fetchLegalDocument(slug);
  if (!doc) notFound();

  return (
    <div className="min-h-screen bg-background">
      <JsonLd
        data={legalDocumentJsonLd({
          title: doc.title,
          path: doc.href,
          datePublished: doc.effectiveAt,
          version: doc.consentVersion,
        })}
      />
      <LandingNav />
      <main>
        <LegalDocument doc={doc} />
      </main>
      <LandingFooter />
    </div>
  );
}
