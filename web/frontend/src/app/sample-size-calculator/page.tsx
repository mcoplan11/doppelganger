import type { Metadata } from "next";
import Link from "next/link";
import { BlogShell } from "@/components/blog-shell";
import { SampleSizeCalculator } from "@/components/sample-size-calculator";

export const metadata: Metadata = {
  title: "Sample size calculator for survey experiments (with cost estimate)",
  description:
    "Free sample size and power calculator for survey experiments. Enter your effect size, power, and design to get participants per condition — plus what the study will cost to field on Prolific or MTurk.",
  alternates: { canonical: "/sample-size-calculator" },
  openGraph: {
    type: "website",
    url: "/sample-size-calculator",
    title: "Sample size calculator for survey experiments (with cost estimate)",
    description:
      "How many participants do you need, and what will they cost? A free power and budget calculator for behavioral researchers.",
  },
};

const FAQ: Array<{ q: string; a: string }> = [
  {
    q: "How many participants do I need for a two-condition survey experiment?",
    a: "For a medium effect (Cohen's d = 0.5) at 80% power and two-tailed α = .05, you need about 64 participants per condition (128 total). For a small-to-medium effect (d = 0.25) the requirement jumps to roughly 253 per condition — small effects are expensive to detect.",
  },
  {
    q: "What effect size should I assume?",
    a: "If you have a pilot or a close prior study, use its estimate — conservatively, since published effects are inflated by selection. With no prior information, powering for d = 0.3–0.5 is a common range for behavioral manipulations; assuming d = 0.8 is usually optimistic.",
  },
  {
    q: "What does 80% statistical power mean?",
    a: "If your effect is real and exactly the size you assumed, a study with 80% power has an 80% chance of detecting it at your significance threshold — and a 20% chance of missing it. Use 90% or 95% when a false negative is costly, at the price of a larger sample.",
  },
  {
    q: "How much does a survey study cost to field?",
    a: "Participant payments are minutes × hourly rate × sample size, plus a platform fee (typically 25–40% on Prolific, MTurk, or CloudResearch) and an exclusion buffer of 5–15% for attention-check failures. A 10-minute, two-condition study powered for d = 0.5 at a fair $12/hour runs roughly $350 all-in; powering the same study for d = 0.25 costs about $1,400.",
  },
  {
    q: "Can I use AI respondents instead of this calculation?",
    a: "Not for your final sample — AI respondents don't replace human data. They're useful one step earlier: a cheap pretest to confirm your manipulation moves anything at all and your survey logic works, before you commit to fielding the full powered sample this calculator gives you.",
  },
];

export default function SampleSizeCalculatorPage() {
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: FAQ.map((f) => ({
      "@type": "Question",
      name: f.q,
      acceptedAnswer: { "@type": "Answer", text: f.a },
    })),
  };

  return (
    <BlogShell>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <div className="max-w-3xl mx-auto px-6 pt-16 pb-8">
        <p className="text-xs font-semibold uppercase tracking-wider text-blue-700 mb-3">Free tool</p>
        <h1 className="font-serif text-3xl sm:text-4xl font-bold text-slate-900 mb-3 leading-tight">
          Sample size calculator for survey experiments
        </h1>
        <p className="text-slate-600 mb-8 leading-relaxed">
          How many participants does your study need — and what will they cost? Enter your expected
          effect size, power, and design. The math follows the standard two-sample t-test power
          calculation (the same framework as G*Power&apos;s t-test family).
        </p>

        <SampleSizeCalculator />

        <article className="max-w-2xl">
          <h2 className="font-serif text-2xl font-bold text-slate-900 mt-12 mb-3">How the calculation works</h2>
          <p className="text-slate-700 leading-relaxed mb-4">
            For a two-group comparison, the required sample per group is approximately{" "}
            <em>
              n = 2(z<sub>α/2</sub> + z<sub>power</sub>)² / d²
            </em>{" "}
            (with a small-sample correction), where <em>d</em> is Cohen&apos;s standardized mean
            difference. The term to respect is the <em>d²</em> in the denominator: halving your
            expected effect size <strong>quadruples</strong> the sample you need. That&apos;s why an
            honest effect-size guess matters more than any other input, and why our{" "}
            <Link href="/blog/how-many-participants-do-i-need" className="text-blue-700 hover:text-blue-800 underline underline-offset-2">
              power-analysis primer
            </Link>{" "}
            warns against estimating effect sizes from tiny pilots.
          </p>
          <p className="text-slate-700 leading-relaxed mb-4">
            The cost estimate multiplies your recruited sample (powered N plus an exclusion buffer)
            by per-participant pay and the platform&apos;s service fee. For the full breakdown of
            where study budgets actually go, see{" "}
            <Link href="/blog/what-does-a-survey-study-cost" className="text-blue-700 hover:text-blue-800 underline underline-offset-2">
              what a behavioral study really costs
            </Link>
            .
          </p>
          <p className="text-slate-700 leading-relaxed mb-4">
            This calculator covers the workhorse case: a t-test comparison between two conditions
            (or a paired within-subjects design), extended to multi-condition studies by powering
            each pairwise cell. For interactions, ANOVA with covariates, or unequal groups, use{" "}
            <a
              href="https://www.gpower.hhu.de/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-700 hover:text-blue-800 underline underline-offset-2"
            >
              G*Power
            </a>{" "}
            — this tool is for the budget conversation, not the registered report.
          </p>

          <div className="bg-blue-50 border border-blue-200 rounded-xl p-6 my-8">
            <p className="text-slate-800 leading-relaxed text-[15px]">
              <strong>Before you spend that budget:</strong> the numbers above assume your effect
              exists and your survey works. Doppelganger runs AI respondents through your actual
              Qualtrics survey first — real randomizer, real branching — so a dead manipulation or
              broken logic costs you a few dollars to find, not your whole sample.{" "}
              <Link href="/" className="text-blue-700 hover:text-blue-800 underline underline-offset-2 font-medium">
                Pretest your survey &rarr;
              </Link>
            </p>
          </div>

          <h2 className="font-serif text-2xl font-bold text-slate-900 mt-10 mb-4">Frequently asked questions</h2>
          {FAQ.map((f) => (
            <div key={f.q} className="mb-5">
              <h3 className="font-semibold text-slate-900 mb-1">{f.q}</h3>
              <p className="text-slate-700 leading-relaxed">{f.a}</p>
            </div>
          ))}

          <p className="text-xs text-slate-400 italic mt-8 border-t border-slate-200 pt-6">
            The sample-size math uses the normal approximation with Guenther&apos;s correction for
            the two-sample t-test; results match G*Power within a participant or two for typical
            inputs. Cost figures are estimates — check current platform fees before budgeting.
          </p>
        </article>
      </div>
    </BlogShell>
  );
}
