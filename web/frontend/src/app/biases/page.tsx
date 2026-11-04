import Link from "next/link";
import type { Metadata } from "next";
import { BIASES, type BiasStatus } from "@/lib/biases";
import { BlogShell } from "@/components/blog-shell";

export const metadata: Metadata = {
  title: "16 classic cognitive biases — and which ones AI respondents reproduce",
  description:
    "The classic heuristics-and-biases experiments — framing, anchoring, sunk cost, the Linda problem — each explained with its original study and our benchmark data on whether AI survey respondents show the same bias.",
  alternates: { canonical: "/biases" },
  openGraph: {
    type: "website",
    url: "/biases",
    title: "16 classic cognitive biases — and which ones AI respondents reproduce",
    description:
      "Every classic bias from our Twin-2K-500 replication benchmark: the original experiment, a concrete example, and whether AI respondents reproduce it.",
  },
};

const BADGE: Record<BiasStatus, { label: string; cls: string }> = {
  yes: { label: "Reproduced", cls: "text-green-700 bg-green-50 border-green-200" },
  partial: { label: "Partial", cls: "text-amber-700 bg-amber-50 border-amber-200" },
  no: { label: "Not reproduced", cls: "text-slate-600 bg-slate-100 border-slate-300" },
};

export default function BiasesIndex() {
  return (
    <BlogShell>
      <div className="max-w-3xl mx-auto px-6 pt-16 pb-8">
        <p className="text-xs font-semibold uppercase tracking-wider text-blue-700 mb-3">Reference</p>
        <h1 className="font-serif text-3xl sm:text-4xl font-bold text-slate-900 mb-4 leading-tight">
          The classic cognitive biases — and which ones AI respondents reproduce
        </h1>
        <p className="text-slate-600 leading-relaxed mb-3">
          These are the experiments that built behavioral science: framing, anchoring, the Linda
          problem, sunk cost, the endowment effect. We ran all of them through AI survey
          respondents as part of our{" "}
          <Link href="/research" className="text-blue-700 hover:text-blue-800 underline underline-offset-2">
            Twin-2K-500 replication benchmark
          </Link>{" "}
          — an ensemble of large language models, roughly 150 respondents per condition — and
          scored each against the original human finding.
        </p>
        <p className="text-slate-600 leading-relaxed mb-10">
          Each page below gives the textbook definition, the classic study, a concrete example, and
          our replication data — including the two effects AI respondents <em>don&apos;t</em> fully
          show, which mark the honest limits of AI pretesting.
        </p>

        <ul className="space-y-4">
          {BIASES.map((b) => {
            const badge = BADGE[b.status];
            return (
              <li key={b.slug} className="border border-slate-200 rounded-xl p-5 hover:border-slate-300 transition">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <Link
                      href={`/biases/${b.slug}`}
                      className="font-semibold text-lg text-slate-900 hover:text-blue-700"
                    >
                      {b.name}
                    </Link>
                    <p className="text-sm text-slate-600 leading-relaxed mt-1">{b.definition.split(". ")[0]}.</p>
                  </div>
                  <span
                    className={`shrink-0 text-xs font-semibold uppercase tracking-wider border rounded-full px-3 py-1 ${badge.cls}`}
                  >
                    {badge.label}
                  </span>
                </div>
              </li>
            );
          })}
        </ul>

        <p className="text-sm text-slate-500 leading-relaxed mt-10">
          Scoreboard: the ensemble reproduced 15.5 of 17 experiments (91%) — the endowment effect
          partially, dominance neglect not at all. Methodology, statistics, and limitations in the{" "}
          <Link href="/research" className="text-blue-700 hover:text-blue-800 underline underline-offset-2">
            technical report
          </Link>
          .
        </p>
      </div>
    </BlogShell>
  );
}
