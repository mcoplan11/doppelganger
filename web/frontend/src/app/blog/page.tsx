import Link from "next/link";
import type { Metadata } from "next";
import { POSTS, formatDate } from "@/lib/posts";
import { BlogShell } from "@/components/blog-shell";

export const metadata: Metadata = {
  title: "Blog",
  description:
    "Practical guides on survey pretesting, AI respondents, statistical power, and running behavioral studies that hold up.",
  alternates: { canonical: "/blog" },
  openGraph: {
    type: "website",
    url: "/blog",
    title: "The Doppelganger blog",
    description:
      "Practical guides on survey pretesting, AI respondents, statistical power, and running behavioral studies that hold up.",
  },
};

export default function BlogIndex() {
  // Newest first. Dates are ISO strings, so lexicographic sort is chronological.
  const posts = [...POSTS].sort((a, b) => (a.date < b.date ? 1 : -1));

  return (
    <BlogShell>
      <section className="max-w-3xl mx-auto px-6 pt-16 pb-8">
        <h1 className="font-serif text-4xl font-bold mb-3 text-slate-900">The Doppelganger blog</h1>
        <p className="text-lg text-slate-600 leading-relaxed">
          Practical guides on pretesting, AI respondents, and running behavioral studies that hold up.
        </p>
      </section>

      <section className="max-w-3xl mx-auto px-6 pb-16 divide-y divide-slate-200">
        {posts.map((post) => (
          <article key={post.slug} className="py-8 first:pt-0">
            <Link href={`/blog/${post.slug}`} className="group block">
              <h2 className="font-serif text-2xl font-bold text-slate-900 group-hover:text-blue-700 transition mb-2">
                {post.title}
              </h2>
              <p className="text-slate-600 mb-3 leading-relaxed">{post.description}</p>
              <span className="text-sm text-slate-400">
                {formatDate(post.date)} · {post.readMinutes} min read
              </span>
            </Link>
          </article>
        ))}
      </section>
    </BlogShell>
  );
}
