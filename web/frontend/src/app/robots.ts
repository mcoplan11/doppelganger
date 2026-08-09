import type { MetadataRoute } from "next";

const SITE = "https://doppelgangerlabs.com";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      // Authenticated app surfaces have no SEO value and shouldn't be crawled.
      disallow: ["/dashboard", "/auth/", "/run/"],
    },
    sitemap: `${SITE}/sitemap.xml`,
    host: SITE,
  };
}
