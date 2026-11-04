import Link from "next/link";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { BIASES, getBias, type BiasStatus } from "@/lib/biases";
import { BlogShell } from "@/components/blog-shell";

export function generateStaticParams() {
  return BIASES.map((b) => ({ slug: b.slug }));
}

// Next 16: params is a Promise and must be awaited.
export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const bias = getBias(slug);
  if (!bias) return {};
  const url = `/biases/${bias.slug}`;
  return {
    title: `${bias.title} | Definition, classic study & AI replication`,
    description: bias.description,
    alternates: { canonical: url },
    openGraph: { type: "article", url, title: bias.title, description: bias.description },
    twitter: { card: "summary_large_image", title: bias.title, description: bias.description },
  };
}

const STATUS_LABEL: Record<BiasStatus, string> = {
  yes: "Reproduced in AI respondents",
  partial: "Partially reproduced in AI respondents",
  no: "Not reproduced in AI respondents",
};
const STATUS_CLS: Record<BiasStatus, string> = {
  yes: "text-green-700 bg-green-50 border-green-200",
  partial: "text-amber-700 bg-amber-50 border-amber-200",
  no: "text-slate-600 bg-slate-100 border-slate-300",
};

function H2({ children }: { children: React.ReactNode }) {
  return <h2 className="font-serif text-2xl font-bold text-slate-900 mt-10 mb-3">{children}</h2>;
}
function P({ children }: { children: React.ReactNode }) {
  return <p className="text-slate-700 leading-relaxed mb-4">{children}</p>;
}

export default async function BiasPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const bias = getBias(slug);
  if (!bias) notFound();

  const related = bias.related
    .map((s) => getBias(s))
    .filter((b): b is NonNullable<typeof b> => Boolean(b));

  const SITE = "https://doppelgangerlabs.com";
  const jsonLd = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "Article",
        headline: bias.title,
        description: bias.description,
        url: `${SITE}/biases/${bias.slug}`,
        mainEntityOfPage: `${SITE}/biases/${bias.slug}`,
        author: { "@id": `${SITE}/#organization` },
        publisher: { "@id": `${SITE}/#organization` },
      },
      {
        "@type": "BreadcrumbList",
        itemListElement: [
          { "@type": "ListItem", position: 1, name: "Home", item: SITE },
          { "@type": "ListItem", position: 2, name: "Biases", item: `${SITE}/biases` },
          { "@type": "ListItem", position: 3, name: bias.name, item: `${SITE}/biases/${bias.slug}` },
        ],
      },
    ],
  };

  return (
    <BlogShell>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <article className="max-w-2xl mx-auto px-6 pt-16 pb-8">
        <Link href="/biases" className="text-sm font-medium text-blue-700 hover:text-blue-800">
          ← All biases
        </Link>
        <h1 className="font-serif text-3xl sm:text-4xl font-bold text-slate-900 mt-6 mb-4 leading-tight">
          {bias.title}
        </h1>
        <span
          className={`inline-block text-xs font-semibold uppercase tracking-wider border rounded-full px-3 py-1 mb-8 ${STATUS_CLS[bias.status]}`}
        >
          {STATUS_LABEL[bias.status]}
        </span>

        <P>{bias.definition}</P>

        <H2>The classic experiment</H2>
        <P>{bias.classicStudy}</P>

        <H2>Where you&apos;ll see it</H2>
        <P>{bias.example}</P>

        <H2>Do AI survey respondents show it?</H2>
        <P>{bias.aiResult}</P>
        <P>
          <em>
            Result from our replication benchmark on the Twin-2K-500 battery — 17 classic
            experiments, N ≈ 150 AI respondents per condition, run through an ensemble of large
            language models. Full methodology and all 17 results in the{" "}
            <Link href="/research" className="text-blue-700 hover:text-blue-800 underline underline-offset-2">
              technical report
            </Link>
            .
          </em>
        </P>

        <H2>What this means for your survey</H2>
        <P>{bias.surveyTip}</P>

        <div className="bg-blue-50 border border-blue-200 rounded-xl p-6 my-8">
          <p className="text-slate-800 leading-relaxed text-[15px]">
            <strong>Pretest your own study:</strong> Doppelganger runs AI respondents through your
            actual Qualtrics survey — your randomizer, your branching — so you can see whether your
            manipulation moves anything before you pay for participants.{" "}
            <Link href="/" className="text-blue-700 hover:text-blue-800 underline underline-offset-2 font-medium">
              Try it free &rarr;
            </Link>
          </p>
        </div>

        <aside className="mt-12 border-t border-slate-200 pt-8">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-4">Related biases</h2>
          <ul className="space-y-3">
            {related.map((b) => (
              <li key={b.slug}>
                <Link
                  href={`/biases/${b.slug}`}
                  className="text-blue-700 hover:text-blue-800 font-medium underline underline-offset-2"
                >
                  {b.name}
                </Link>
              </li>
            ))}
            <li>
              <Link
                href="/biases"
                className="text-blue-700 hover:text-blue-800 font-medium underline underline-offset-2"
              >
                All 16 biases: which ones do AI respondents reproduce?
              </Link>
            </li>
          </ul>
        </aside>
      </article>
    </BlogShell>
  );
}
