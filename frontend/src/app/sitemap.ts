import type { MetadataRoute } from "next";

import { SITE } from "@lib/seo";
import { fetchLegalDocuments } from "@lib/legal.server";
import { ROUTES } from "@lib/routes";

// Public sitemap: marketing + legal routes only. Legal slugs come from the backend.
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const staticEntries: MetadataRoute.Sitemap = [
    { url: abs("/"), changeFrequency: "weekly", priority: 1 },
    { url: abs(ROUTES.ABOUT), changeFrequency: "monthly", priority: 0.6 },
    { url: abs("/sample-report"), changeFrequency: "monthly", priority: 0.6 },
  ];

  let legalEntries: MetadataRoute.Sitemap = [];
  try {
    const docs = await fetchLegalDocuments();
    legalEntries = docs.map((doc) => ({
      url: abs(doc.href),
      lastModified: doc.effectiveAt ? new Date(doc.effectiveAt) : undefined,
      changeFrequency: "yearly",
      priority: 0.3,
    }));
  } catch {
    // If the backend is unreachable, still serve the static routes.
    legalEntries = [];
  }

  return [...staticEntries, ...legalEntries];
}

function abs(path: string): string {
  return new URL(path, SITE.url).toString();
}
