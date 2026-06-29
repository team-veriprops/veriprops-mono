import type { MetadataRoute } from "next";

import { SITE } from "@lib/seo";

/**
 * Crawl rules: public marketing + legal pages are allowed; authenticated and
 * internal surfaces are disallowed (PRD R1.6). VID-lookup pages are gated to
 * `noindex` per-page until COMPLETED (Phase 13).
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: ["/portal", "/admin", "/agents", "/account", "/auth", "/api"],
    },
    sitemap: new URL("/sitemap.xml", SITE.url).toString(),
    host: SITE.url,
  };
}
