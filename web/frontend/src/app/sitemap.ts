import type { MetadataRoute } from "next";
import { POSTS } from "@/lib/posts";
import { BIASES } from "@/lib/biases";

const SITE = "https://doppelgangerlabs.com";

export default function sitemap(): MetadataRoute.Sitemap {
  const staticRoutes: MetadataRoute.Sitemap = [
    { url: `${SITE}/`, changeFrequency: "weekly", priority: 1 },
    { url: `${SITE}/research`, changeFrequency: "monthly", priority: 0.9 },
    { url: `${SITE}/blog`, changeFrequency: "weekly", priority: 0.8 },
    { url: `${SITE}/security`, changeFrequency: "monthly", priority: 0.6 },
    { url: `${SITE}/sample-size-calculator`, changeFrequency: "monthly", priority: 0.8 },
    { url: `${SITE}/biases`, changeFrequency: "monthly", priority: 0.8 },
    ...BIASES.map((b) => ({
      url: `${SITE}/biases/${b.slug}`,
      changeFrequency: "monthly" as const,
      priority: 0.7,
    })),
  ];

  const postRoutes: MetadataRoute.Sitemap = POSTS.map((post) => ({
    url: `${SITE}/blog/${post.slug}`,
    lastModified: post.date,
    changeFrequency: "monthly",
    priority: 0.7,
  }));

  return [...staticRoutes, ...postRoutes];
}
