import type { MetadataRoute } from "next";

import { SITE } from "@lib/seo";

// Allow marketing + legal pages; disallow authenticated and internal surfaces.
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
