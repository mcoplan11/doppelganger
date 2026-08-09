import Link from "next/link";
import type { ReactNode } from "react";

// Blog content lives here as typed data + JSX bodies. No markdown/MDX dependency —
// each post's Body is a small server component rendered by the [slug] route. Add a
// new post by appending to POSTS; it is automatically picked up by the blog index,
// the [slug] route (generateStaticParams), and the sitemap.

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

/** Format an ISO `YYYY-MM-DD` date deterministically (no locale/timezone surprises). */
export function formatDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return `${MONTHS[m - 1]} ${d}, ${y}`;
}

export type Post = {
  slug: string;
  title: string;
  description: string;
  date: string; // ISO YYYY-MM-DD
  readMinutes: number;
  Body: () => ReactNode;
};

// --- Shared typographic building blocks (keeps every post visually consistent) ---
function P({ children }: { children: ReactNode }) {
  return <p className="text-slate-700 leading-relaxed mb-4">{children}</p>;
}
function H2({ children }: { children: ReactNode }) {
  return <h2 className="font-serif text-2xl font-bold text-slate-900 mt-10 mb-3">{children}</h2>;
}
function Ul({ children }: { children: ReactNode }) {
  return <ul className="list-disc pl-6 space-y-2 mb-4 text-slate-700 leading-relaxed">{children}</ul>;
}
function Ext({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-blue-700 hover:text-blue-800 underline underline-offset-2"
    >
      {children}
    </a>
  );
}

export const POSTS: Post[] = [
  {
    slug: "can-ai-replace-survey-respondents",
    title: "Can AI replace survey respondents? What the evidence says",
    description:
      "We benchmarked AI respondents against a published dataset of 17 classic behavioral experiments. Here's what replicated, what didn't, and how to use AI pretesting honestly.",
    date: "2026-08-09",
    readMinutes: 5,
    Body: () => (
      <>
        <P>
          Survey research is expensive. A single well-powered study on Prolific or MTurk can run
          into the hundreds or thousands of dollars — and if your manipulation doesn&apos;t land or
          your wording confuses people, you often find out only <em>after</em> you&apos;ve paid.
          That&apos;s the problem AI &ldquo;respondents&rdquo; promise to solve: run your study on
          simulated participants first, cheaply, and catch the duds before you field them on humans.
        </P>
        <P>But do AI respondents actually behave like people? We put it to a real test.</P>

        <H2>The benchmark</H2>
        <P>
          We used{" "}
          <Ext href="https://arxiv.org/abs/2505.17479">Twin-2K-500</Ext> (Toubia et al., 2025), a
          published dataset built on the answers of more than 2,000 real people to 17 classic
          heuristics-and-biases experiments — framing effects, the Linda conjunction problem,
          anchoring, sunk-cost, and more. We ran all 17 studies through our AI respondents and
          counted how many of these well-established human effects the model reproduced.
        </P>

        <H2>The result</H2>
        <P>
          Our model reproduced <strong>12 of the 17 effects (about 71%)</strong>. For comparison,
          the AI &ldquo;digital twins&rdquo; built in the original study — models conditioned on each
          real person&apos;s prior answers — reproduced 9. On the same studies, scored the same way,
          our respondents matched <em>more</em> of the known human effects.
        </P>
        <P>
          The practical read: <strong>if your effect is real, there&apos;s a better-than-70% chance
          it will show up in AI respondents too.</strong> That makes an AI pretest a strong early
          signal about whether an idea is worth fielding.
        </P>

        <H2>What it does <em>not</em> mean</H2>
        <P>We think the honest framing matters more than the headline, so here are the limits:</P>
        <Ul>
          <li>
            <strong>It is not a replacement for human data.</strong> Five of the 17 effects
            didn&apos;t replicate. AI respondents can be too rational and miss some biases entirely.
          </li>
          <li>
            <strong>A null isn&apos;t a death sentence, and a hit isn&apos;t proof.</strong> Use the
            pretest to prioritize and de-risk — not to make the final call.
          </li>
          <li>
            <strong>Text only, for now.</strong> Our respondents read and answer written questions;
            they can&apos;t yet see image or video stimuli.
          </li>
        </Ul>

        <H2>How to use it</H2>
        <P>
          Treat an AI pretest the way you&apos;d treat a pilot: a cheap first look. Run your survey
          through AI respondents to catch broken skip logic, dead-on-arrival manipulations, and
          confusing wording — then spend your participant budget on the studies that already show
          signs of life. That&apos;s the whole idea behind Doppelganger.
        </P>
        <P>
          For the full methodology, per-experiment results, and honest limitations, see our{" "}
          <Link
            href="/research"
            className="text-blue-700 hover:text-blue-800 underline underline-offset-2"
          >
            technical report
          </Link>
          .
        </P>
      </>
    ),
  },
  {
    slug: "how-to-pretest-a-survey",
    title: "How to pretest a survey before you pay for participants",
    description:
      "A practical checklist for catching broken logic, dead manipulations, and confusing wording before you spend your participant budget.",
    date: "2026-08-07",
    readMinutes: 4,
    Body: () => (
      <>
        <P>
          Most wasted participant budget isn&apos;t wasted on bad ideas — it&apos;s wasted on good
          ideas that were fielded before the survey itself was ready. A pretest is the cheapest
          insurance you can buy. Here&apos;s what to check before a single real participant sees your
          study.
        </P>

        <H2>1. Walk every branch</H2>
        <P>
          Skip logic and randomized conditions are where surveys quietly break. Confirm that every
          arm routes correctly, that no one gets stranded, and that embedded data carries through to
          the end. Bugs here silently corrupt your data rather than throwing an error.
        </P>

        <H2>2. Check that your manipulation actually moves something</H2>
        <P>
          The most expensive failure is a manipulation that reads clearly to you but does nothing to
          respondents. Look at whether your conditions produce a difference on the manipulation check
          <em>before</em> you care about the outcome. If the manipulation doesn&apos;t move, nothing
          downstream will.
        </P>

        <H2>3. Read your wording like a stranger</H2>
        <Ul>
          <li>Double-barreled questions (&ldquo;how clear and useful was this?&rdquo;).</li>
          <li>Leading or loaded phrasing that telegraphs the &ldquo;right&rdquo; answer.</li>
          <li>Scales with missing or overlapping options.</li>
          <li>Jargon that means something to you but not to your sample.</li>
        </Ul>

        <H2>4. Estimate the effect, not just the plumbing</H2>
        <P>
          A pretest can also give you a rough sense of direction and size — enough to decide whether
          the effect is worth powering for. AI respondents are useful here: if a real effect shows up
          in a cheap simulated run, that&apos;s a green light to invest in a proper sample.
        </P>

        <H2>5. Then field with confidence</H2>
        <P>
          Once the logic is clean, the manipulation moves, and the wording is tight, you can spend on
          human participants knowing you&apos;re paying to measure an effect — not to debug a survey.
        </P>
      </>
    ),
  },
  {
    slug: "how-many-participants-do-i-need",
    title: "How many participants do I need? A quick power-analysis primer",
    description:
      "A plain-English guide to sample size and statistical power for behavioral studies — and how to avoid the underpowered pilot trap.",
    date: "2026-08-05",
    readMinutes: 6,
    Body: () => (
      <>
        <P>
          &ldquo;How many participants do I need?&rdquo; is the most common question in study design,
          and the honest answer is: it depends on how big your effect is and how sure you want to be
          that you&apos;ll detect it. Here&apos;s the plain-English version.
        </P>

        <H2>The three levers</H2>
        <Ul>
          <li>
            <strong>Effect size</strong> — how big the difference you&apos;re looking for is. Smaller
            effects need bigger samples. This is the lever people underestimate most.
          </li>
          <li>
            <strong>Power</strong> — your chance of detecting a real effect. Convention is 80%, but
            90% is safer for effects you can&apos;t easily re-run.
          </li>
          <li>
            <strong>Alpha</strong> — your tolerance for a false positive, usually 5%.
          </li>
        </Ul>

        <H2>Rough rules of thumb</H2>
        <P>
          For a simple two-group comparison at 80% power and a medium effect (d ≈ 0.5), you need
          roughly 64 people per condition. Halve the effect (d ≈ 0.25) and that jumps to about 250
          per condition. The takeaway: small effects are expensive, and guessing your effect size is
          the biggest source of underpowered studies.
        </P>

        <H2>Avoid the underpowered-pilot trap</H2>
        <P>
          A common mistake is running a tiny pilot, seeing a &ldquo;promising&rdquo; result, and
          scaling up — when the pilot was too small to mean anything. Pilots are great for checking
          that a study <em>works</em>; they&apos;re unreliable for estimating how big an effect is.
        </P>

        <H2>Where AI pretesting fits</H2>
        <P>
          You can&apos;t derive your final sample size from AI respondents — but you can use a cheap
          AI pretest to sanity-check direction and catch a manipulation that does nothing before you
          commit to a power analysis at all. Use tools like{" "}
          <Ext href="https://www.gpower.hhu.de/">G*Power</Ext> for the formal calculation, and use a
          pretest to make sure the thing you&apos;re powering for is actually there.
        </P>
      </>
    ),
  },
];

export function getPost(slug: string): Post | undefined {
  return POSTS.find((p) => p.slug === slug);
}
