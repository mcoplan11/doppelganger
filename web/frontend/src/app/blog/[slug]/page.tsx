import Link from "next/link";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { POSTS, getPost, formatDate } from "@/lib/posts";
import { BlogShell } from "@/components/blog-shell";

// Pre-render every post at build time.
export function generateStaticParams() {
  return POSTS.map((p) => ({ slug: p.slug }));
}

// Next 16: params is a Promise and must be awaited.
export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const post = getPost(slug);
  if (!post) return {};
  const url = `/blog/${post.slug}`;
  return {
    title: post.title,
    description: post.description,
    alternates: { canonical: url },
    openGraph: {
      type: "article",
      url,
      title: post.title,
      description: post.description,
      publishedTime: post.date,
    },
    twitter: {
      card: "summary_large_image",
      title: post.title,
      description: post.description,
    },
  };
}

export default async function BlogPost({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const post = getPost(slug);
  if (!post) notFound();

  const Body = post.Body;

  // Cross-link to the other posts so readers (and crawlers) move between related
  // pages instead of dead-ending — helps discovery and spreads internal link equity.
  const related = POSTS.filter((p) => p.slug !== post.slug);

  const SITE = "https://doppelgangerlabs.com";
  const jsonLd = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "BlogPosting",
        headline: post.title,
        description: post.description,
        datePublished: post.date,
        dateModified: post.date,
        url: `${SITE}/blog/${post.slug}`,
        mainEntityOfPage: `${SITE}/blog/${post.slug}`,
        author: { "@id": `${SITE}/#organization` },
        publisher: { "@id": `${SITE}/#organization` },
      },
      {
        "@type": "BreadcrumbList",
        itemListElement: [
          { "@type": "ListItem", position: 1, name: "Home", item: SITE },
          { "@type": "ListItem", position: 2, name: "Blog", item: `${SITE}/blog` },
          { "@type": "ListItem", position: 3, name: post.title, item: `${SITE}/blog/${post.slug}` },
        ],
      },
    ],
  };

  return (
    <BlogShell>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <article className="max-w-2xl mx-auto px-6 pt-16 pb-8">
        <Link href="/blog" className="text-sm font-medium text-blue-700 hover:text-blue-800">
          ← All posts
        </Link>
        <h1 className="font-serif text-3xl sm:text-4xl font-bold text-slate-900 mt-6 mb-3 leading-tight">
          {post.title}
        </h1>
        <p className="text-sm text-slate-400 mb-8">
          {formatDate(post.date)} · {post.readMinutes} min read
        </p>

        <Body />

        <div className="mt-12 border-t border-slate-200 pt-8">
          <Link
            href="/#login"
            className="inline-block bg-blue-700 hover:bg-blue-800 text-white font-semibold px-6 py-3 rounded-lg transition"
          >
            Pretest a survey free →
          </Link>
        </div>

        <aside className="mt-12 border-t border-slate-200 pt-8">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-4">
            Keep reading
          </h2>
          <ul className="space-y-3">
            {related.map((p) => (
              <li key={p.slug}>
                <Link
                  href={`/blog/${p.slug}`}
                  className="text-blue-700 hover:text-blue-800 font-medium underline underline-offset-2"
                >
                  {p.title}
                </Link>
              </li>
            ))}
            <li>
              <Link
                href="/research"
                className="text-blue-700 hover:text-blue-800 font-medium underline underline-offset-2"
              >
                Research report: Do LLMs reproduce classic human decision biases?
              </Link>
            </li>
          </ul>
        </aside>
      </article>
    </BlogShell>
  );
}
