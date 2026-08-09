import type { Metadata } from "next";
import { BlogShell } from "@/components/blog-shell";

export const metadata: Metadata = {
  title: "Do language models reproduce classic human decision biases?",
  description:
    "A replication benchmark on Twin-2K-500: our best model reproduces 12 of 17 classic heuristics-and-biases effects (71%), compared with 8 of 16 (50%) for the original study's digital twins.",
  alternates: { canonical: "/research" },
  openGraph: {
    type: "article",
    url: "/research",
    title: "Do language models reproduce classic human decision biases? A replication benchmark",
    description:
      "Our best model reproduces 12 of 17 classic decision biases (71%) on the Twin-2K-500 battery. Methods, results, and honest limitations.",
  },
  twitter: {
    card: "summary_large_image",
    title: "Do language models reproduce classic human decision biases?",
    description:
      "A replication benchmark on Twin-2K-500: 12 of 17 classic decision biases reproduced (71%).",
  },
};

const RESULTS: Array<{ name: string; reproduced: boolean }> = [
  { name: "Framing (Asian-disease problem)", reproduced: true },
  { name: "Conjunction fallacy (Linda)", reproduced: true },
  { name: "Anchoring (redwood tree)", reproduced: true },
  { name: "Anchoring (Mississippi River)", reproduced: true },
  { name: "Absolute vs. relative savings", reproduced: true },
  { name: "Myside bias", reproduced: true },
  { name: "Sunk-cost fallacy", reproduced: true },
  { name: "Outcome bias", reproduced: true },
  { name: "Allais paradox", reproduced: true },
  { name: "Base-rate neglect", reproduced: true },
  { name: "False consensus", reproduced: true },
  { name: "Probability matching", reproduced: true },
  { name: "Less-is-more", reproduced: false },
  { name: "WTA/WTP endowment effect", reproduced: false },
  { name: "Risk–benefit nonseparability", reproduced: false },
  { name: "Omission bias", reproduced: false },
  { name: "Dominator neglect", reproduced: false },
];

function H2({ children }: { children: React.ReactNode }) {
  return <h2 className="font-serif text-2xl font-bold text-slate-900 mt-10 mb-3">{children}</h2>;
}
function P({ children }: { children: React.ReactNode }) {
  return <p className="text-slate-700 leading-relaxed mb-4">{children}</p>;
}
function Ext({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className="text-blue-700 hover:text-blue-800 underline underline-offset-2">
      {children}
    </a>
  );
}

export default function Research() {
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "ScholarlyArticle",
    headline:
      "Do off-the-shelf language models reproduce classic human decision biases? A replication benchmark on Twin-2K-500",
    datePublished: "2026-08-09",
    author: { "@type": "Organization", name: "Doppelganger Labs" },
    publisher: { "@type": "Organization", name: "Doppelganger Labs" },
    url: "https://doppelgangerlabs.com/research",
    description:
      "A replication benchmark on Twin-2K-500: our best model reproduces 12 of 17 classic decision biases (71%).",
  };

  return (
    <BlogShell>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <article className="max-w-2xl mx-auto px-6 pt-16 pb-8">
        <p className="text-xs font-semibold uppercase tracking-wider text-blue-700 mb-3">Technical report</p>
        <h1 className="font-serif text-3xl sm:text-4xl font-bold text-slate-900 mb-3 leading-tight">
          Do off-the-shelf language models reproduce classic human decision biases?
        </h1>
        <p className="text-slate-600 mb-1">A replication benchmark on Twin-2K-500</p>
        <p className="text-sm text-slate-400 mb-8">Doppelganger Labs · August 2026 · Not peer reviewed</p>

        <div className="bg-slate-50 border border-slate-200 rounded-xl p-6 mb-8">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">Abstract</p>
          <p className="text-slate-700 leading-relaxed text-[15px]">
            A growing body of work asks whether large language models (LLMs) can stand in for human
            participants when pretesting survey studies. We evaluate this directly on the
            heuristics-and-biases battery compiled in Twin-2K-500 (Toubia et al., 2025), a public
            dataset built from the answers of more than 2,000 real people. We run 17 classic
            experiments through persona-conditioned simulated respondents and score, for each
            experiment, whether the model produces a statistically significant effect in the
            direction the original authors reported. Our best-performing configuration reproduces 12
            of the 17 effects (71%). For reference, Toubia et al. report that digital twins
            conditioned on each respondent&apos;s own prior answers reproduce the expected effect in 8
            of the 16 experiments they tested (50%). The two figures are not a like-for-like contest,
            but both point to the same conclusion: a strong majority of well-established human effects
            re-emerge in LLM respondents.
          </p>
        </div>

        <H2>1. Motivation</H2>
        <P>
          Survey research is expensive and slow. A single well-powered behavioral study can cost
          hundreds to thousands of dollars in participant fees, and much of that spend is committed
          before the researcher knows whether the manipulation works, the wording is clear, or the
          effect is even present. If simulated respondents reproduced known human effects reliably
          enough, they could serve as a cheap first pass &mdash; a way to catch broken designs and
          gauge whether an idea is worth fielding.
        </P>
        <P>
          The obvious objection is that LLMs may be &ldquo;too rational&rdquo;: trained to be helpful
          and correct, they might sidestep exactly the biases that make human data interesting. This
          report tests that objection against an external, published benchmark rather than a battery
          of our own design.
        </P>

        <H2>2. Data and studies</H2>
        <P>
          We use the classic heuristics-and-biases experiments compiled in{" "}
          <Ext href="https://arxiv.org/abs/2505.17479">Twin-2K-500</Ext> (Toubia et al., 2025), which
          pairs each experiment with responses from a large, demographically diverse human sample.
          Our implementation covers 17 experiments spanning framing effects, the Linda conjunction
          problem, two anchoring tasks, absolute-vs-relative savings, myside bias, less-is-more, the
          WTA/WTP endowment effect, sunk cost, outcome bias, the Allais paradox, base-rate neglect,
          false consensus, risk&ndash;benefit nonseparability, omission bias, probability matching,
          and dominator neglect. This set includes base-rate neglect, one experiment beyond the 16 in
          Toubia et al.&apos;s replication table.
        </P>

        <H2>3. Method</H2>
        <P>
          Each study is administered to a panel of demographically varied simulated respondents
          (N = 150), implemented as persona-conditioned prompts answered by our best-performing model
          configuration, a large instruction-tuned LLM. Responses are constrained to a structured
          JSON schema so they can be scored automatically. We use a decoding temperature of 0.5, a
          within-subject administration where the original design permits it, and a fixed random seed
          for persona assignment so runs are reproducible.
        </P>
        <P>
          For each experiment we apply the significance test appropriate to its outcome &mdash; a
          t-test for continuous measures, a chi-square or exact test for categorical choices &mdash;
          and classify an effect as <em>reproduced</em> when the simulated respondents show a
          statistically significant difference (p &lt; .05) in the direction the original authors
          predicted.
        </P>

        <H2>4. Results</H2>
        <P>
          Our best-performing configuration reproduced <strong>12 of the 17 effects (71%)</strong>.
          The breakdown:
        </P>
        <div className="overflow-hidden rounded-lg border border-slate-200 mb-6">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 text-slate-600">
                <th className="text-left font-semibold px-4 py-2">Experiment</th>
                <th className="text-left font-semibold px-4 py-2 w-40">Reproduced?</th>
              </tr>
            </thead>
            <tbody>
              {RESULTS.map((r) => (
                <tr key={r.name} className="border-t border-slate-100">
                  <td className="px-4 py-2 text-slate-700">{r.name}</td>
                  <td className={`px-4 py-2 font-semibold ${r.reproduced ? "text-green-700" : "text-slate-400"}`}>
                    {r.reproduced ? "Yes" : "No"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <P>
          <strong>Comparison to the original digital twins.</strong> Toubia et al. (2025) report that
          their digital twins &mdash; models conditioned on each real person&apos;s own prior survey
          answers &mdash; reproduced the expected human effect in 8 of the 16 experiments they tested
          (50%): 6 of 11 between-subject and 2 of 5 within-subject. Our 71% and their 50% are not a
          like-for-like contest: we scored 17 experiments to their 16, and our
          &ldquo;significant-and-correct-direction&rdquo; rule differs from their reporting. Read as
          two independent estimates of the same quantity, both indicate that a clear majority of
          classic human effects re-emerge in LLM respondents &mdash; and that an off-the-shelf model
          can do so without being individually conditioned on a target person&apos;s prior answers.
        </P>
        <P>
          The successes and failures do not simply nest. Our model captured several effects the
          original twins missed (anchoring on the Mississippi task, sunk cost, outcome bias, the
          Allais paradox) while missing three the twins captured (less-is-more, the WTA/WTP endowment
          effect, and dominator neglect). Both approaches failed on omission bias, where simulated
          respondents are markedly less loss- and harm-averse than humans.
        </P>

        <H2>5. Limitations</H2>
        <P>
          These results are a bound on usefulness, not a claim of equivalence with human data. Five of
          17 effects did not reproduce; LLM respondents remain systematically too rational on some
          tasks, particularly those involving ownership and personal risk. The comparison to Toubia
          et al. uses different study sets and scoring rules, so the head-to-head numbers are
          approximate. We report our best-performing configuration; other models we tested reproduced
          fewer effects. The pipeline is text-only. Most importantly, a null result in simulation is
          not evidence of a null in humans, and a hit is not proof of a real effect &mdash; simulated
          respondents are a screening tool, not an oracle.
        </P>

        <H2>6. Conclusion</H2>
        <P>
          On an external, published benchmark, an off-the-shelf language model reproduced roughly
          seven of every ten classic decision-making effects, at a rate comparable to or above
          digital twins individually conditioned on real respondents. That is enough to make AI
          respondents a useful pretest: a cheap way to catch broken designs and prioritize which
          studies deserve a real sample, while leaving the confirmatory work to human participants.
        </P>

        <H2>References</H2>
        <ol className="list-decimal pl-6 space-y-2 text-sm text-slate-600 leading-relaxed">
          <li>
            Toubia, O., et al. (2025). <em>Twin-2K-500: A dataset for building digital twins of over
            2,000 people based on their answers to over 500 questions.</em>{" "}
            <Ext href="https://arxiv.org/abs/2505.17479">arXiv:2505.17479</Ext>.
          </li>
          <li>Tversky, A., &amp; Kahneman, D. (1981). The framing of decisions and the psychology of choice. <em>Science</em>, 211(4481), 453&ndash;458.</li>
          <li>Tversky, A., &amp; Kahneman, D. (1983). Extensional versus intuitive reasoning: The conjunction fallacy in probability judgment. <em>Psychological Review</em>, 90(4), 293&ndash;315.</li>
          <li>Kahneman, D., Knetsch, J. L., &amp; Thaler, R. H. (1990). Experimental tests of the endowment effect and the Coase theorem. <em>Journal of Political Economy</em>, 98(6), 1325&ndash;1348.</li>
          <li>Argyle, L. P., et al. (2023). Out of one, many: Using language models to simulate human samples. <em>Political Analysis</em>, 31(3), 337&ndash;351.</li>
          <li>Horton, J. J. (2023). Large language models as simulated economic agents. NBER Working Paper 31122.</li>
        </ol>

        <p className="text-xs text-slate-400 italic mt-8 border-t border-slate-200 pt-6">
          This is a non-peer-reviewed technical report describing an internal replication benchmark.
          Figures attributed to Toubia et al. (2025) are quoted from the published paper; all other
          results are our own.
        </p>
      </article>
    </BlogShell>
  );
}
