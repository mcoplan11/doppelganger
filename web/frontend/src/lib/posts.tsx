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
    slug: "qualtrics-generate-test-responses",
    title: "Qualtrics test responses: what the built-in generator does — and what it can't catch",
    description:
      "Qualtrics can fill your survey with random test responses in one click. Here's what that's good for, what it misses, and when you need respondents that actually read the questions.",
    date: "2026-11-02",
    readMinutes: 5,
    Body: () => (
      <>
        <P>
          Qualtrics has a built-in way to test a survey before you field it: open your project, go
          to <strong>Tools &rarr; Review &rarr; Generate test responses</strong>, choose a number,
          and Qualtrics fills your survey with automated responses. It&apos;s free, instant, and
          every researcher should run it at least once before launching. But it&apos;s important to
          understand what those test responses are — and what they aren&apos;t.
        </P>

        <H2>What the built-in generator is good for</H2>
        <P>
          Qualtrics test responses are <strong>random</strong>: the generator walks through your
          survey picking arbitrary answers. That makes it a solid plumbing check. Use it to
          confirm that:
        </P>
        <Ul>
          <li>Every question records data under the right variable name.</li>
          <li>Your dataset has the columns and format you expect before real data arrives.</li>
          <li>The survey can be completed end to end without a hard error.</li>
          <li>Randomized conditions are actually being assigned.</li>
        </Ul>

        <H2>What random responses can&apos;t tell you</H2>
        <P>
          Because the answers are random, they carry no signal. Random test data can&apos;t tell
          you whether:
        </P>
        <Ul>
          <li>
            <strong>Your manipulation does anything.</strong> Random respondents in condition A and
            condition B will answer identically, by construction. The most expensive survey failure
            — a manipulation that doesn&apos;t move anyone — is invisible.
          </li>
          <li>
            <strong>Your wording is confusing.</strong> A random clicker never gets confused. A
            double-barreled question, a reversed scale, or an ambiguous vignette sails through.
          </li>
          <li>
            <strong>Your skip logic makes sense.</strong> Random data exercises branches, but it
            can&apos;t notice that a branch stranded respondents somewhere that makes no sense for
            a human.
          </li>
          <li>
            <strong>Your effect has any signs of life.</strong> There is no direction or size in
            noise.
          </li>
        </Ul>

        <H2>The next step up: respondents that read the survey</H2>
        <P>
          AI respondents sit between random test data and a paid human pilot. They actually read
          each question — vignette, images, scales — and answer in character as personas with
          demographics, which means conditions can differ, confusing wording produces confused
          answers, and a manipulation that does nothing shows up as a flat result{" "}
          <em>before</em> you&apos;ve spent your participant budget. In our{" "}
          <Link
            href="/research"
            className="text-blue-700 hover:text-blue-800 underline underline-offset-2"
          >
            benchmark on 17 classic behavioral experiments
          </Link>
          , an ensemble of AI respondents reproduced about 91% of known human effects — far from
          perfect, but a dramatically stronger pretest signal than random clicks.
        </P>

        <H2>A sensible testing ladder</H2>
        <Ul>
          <li>
            <strong>1. Preview yourself</strong> — catch typos and obvious breakage.
          </li>
          <li>
            <strong>2. Qualtrics test responses</strong> — verify the data pipeline and variable
            names.
          </li>
          <li>
            <strong>3. AI respondents</strong> — check that the manipulation moves, the logic makes
            sense, and the effect shows signs of life.
          </li>
          <li>
            <strong>4. A small human pilot, then the real sample</strong> — the confirmatory steps
            that only people can provide.
          </li>
        </Ul>
        <P>
          Steps 1 and 2 are free inside Qualtrics. Step 3 is what Doppelganger does: point it at
          your Qualtrics survey and it runs AI respondents through your actual survey flow —
          randomizer, branching, and all — for a few dollars instead of a few hundred.
        </P>
      </>
    ),
  },
  {
    slug: "qualtrics-api-access-university",
    title: "How to get Qualtrics API access at a university (and what to tell your admin)",
    description:
      "A step-by-step guide to getting your Qualtrics API token on a university brand account — including a copy-paste request email for your Qualtrics administrator.",
    date: "2026-10-28",
    readMinutes: 4,
    Body: () => (
      <>
        <P>
          If you&apos;re a student or faculty member trying to use the Qualtrics API — for a
          pretesting tool, a data pipeline, or your own scripts — you&apos;ve probably hit this
          wall: you open <strong>Account Settings &rarr; Qualtrics IDs</strong> and the API section
          is missing, or there&apos;s no &ldquo;Generate Token&rdquo; button. That&apos;s not a bug.
          On university (&ldquo;brand&rdquo;) accounts, API access is a per-user permission that
          your Qualtrics brand administrator has to switch on. Here&apos;s how to get it.
        </P>
        <P>
          <em>
            Update: if you&apos;re here because of Doppelganger specifically, you no longer need
            API access at all — you can upload your survey&apos;s .qsf export directly and skip
            this entire process. The guide below still applies to the API connection mode and any
            other tool that needs a token.
          </em>
        </P>

        <H2>Step 1: Find your brand administrator</H2>
        <P>
          Every university Qualtrics license has one or more brand admins — usually in the
          library, central IT, or the research computing office. Search your university&apos;s site
          for &ldquo;Qualtrics support&rdquo; or ask your department&apos;s IT contact. This is the
          person who can enable the permission; Qualtrics itself can&apos;t do it for you.
        </P>

        <H2>Step 2: Send the request (copy-paste template)</H2>
        <P>Admins approve these routinely. Something like this is all it takes:</P>
        <div className="bg-slate-50 border border-slate-200 rounded-xl p-5 mb-4 text-[15px] text-slate-700 leading-relaxed">
          <p className="mb-2">Subject: Enable Qualtrics API access for my account</p>
          <p className="mb-2">Hi,</p>
          <p className="mb-2">
            Could you please enable the &ldquo;Access API&rdquo; permission for my Qualtrics user
            ([your university email])? I need it to run a survey pretesting tool against a survey I
            own. The tool only reads the survey I point it at and creates a working copy in my own
            account — it doesn&apos;t touch other users&apos; projects or any collected data.
          </p>
          <p>Thank you!</p>
        </div>
        <P>
          If your admin wants specifics about what a third-party tool does with the token, send
          them the tool&apos;s security documentation — for Doppelganger, that&apos;s our{" "}
          <Link
            href="/security"
            className="text-blue-700 hover:text-blue-800 underline underline-offset-2"
          >
            security page
          </Link>
          , which lists every API call we make and what is read versus written.
        </P>

        <H2>Step 3: Generate your token</H2>
        <P>
          Once the permission is on: profile icon &rarr; <strong>Account Settings</strong> &rarr;{" "}
          <strong>Qualtrics IDs</strong> &rarr; under <strong>API</strong>, click{" "}
          <strong>Generate Token</strong>. Copy the token somewhere safe — treat it like a
          password, because it grants the same access your account has.
        </P>

        <H2>Good token hygiene</H2>
        <Ul>
          <li>
            <strong>Tokens are account-level.</strong> Qualtrics doesn&apos;t offer per-survey
            tokens, so only paste yours into tools you have a reason to trust — and read what they
            say they do with it.
          </li>
          <li>
            <strong>Regenerate after one-off uses.</strong> Clicking Generate Token again instantly
            invalidates the old token. If you used a tool for a single pretest, you can kill the
            credential the same afternoon.
          </li>
          <li>
            <strong>Never commit a token to code or share it in email.</strong> Anyone holding it
            is you, as far as Qualtrics is concerned.
          </li>
        </Ul>

        <H2>While you wait for your admin</H2>
        <P>
          Approval usually takes a day or two. It&apos;s a good moment to pretest everything else:
          preview the survey yourself, run Qualtrics&apos;s built-in test responses to check your
          data pipeline, and tighten wording — so that when the token arrives, you&apos;re ready to
          run.
        </P>
      </>
    ),
  },
  {
    slug: "what-are-synthetic-respondents",
    title: "What are synthetic respondents? An honest guide to AI survey participants",
    description:
      "Synthetic respondents, silicon sampling, digital twins — what these terms mean, what the evidence says AI participants can and can't do, and how to use them without fooling yourself.",
    date: "2026-10-22",
    readMinutes: 6,
    Body: () => (
      <>
        <P>
          <strong>Synthetic respondents</strong> are AI systems — today, large language models —
          that answer survey questions as if they were human participants. Instead of recruiting
          people, you prompt a model to adopt a persona (&ldquo;a 34-year-old nurse in Ohio&rdquo;)
          and run it through your questionnaire. The idea now goes by several names:
          &ldquo;silicon sampling,&rdquo; &ldquo;AI participants,&rdquo; &ldquo;digital
          twins,&rdquo; &ldquo;synthetic data.&rdquo; The hype is loud in both directions, so
          here&apos;s what the evidence actually supports.
        </P>

        <H2>The terms, untangled</H2>
        <Ul>
          <li>
            <strong>Synthetic respondents / AI participants</strong> — the umbrella: LLMs answering
            surveys in character, usually conditioned on demographic personas.
          </li>
          <li>
            <strong>Silicon sampling</strong> — the academic term, coined by{" "}
            <Ext href="https://doi.org/10.1017/pan.2023.2">Argyle et al. (2023)</Ext>, for using
            persona-conditioned LLMs to approximate the response distributions of human
            subpopulations.
          </li>
          <li>
            <strong>Digital twins</strong> — a stronger claim: a model conditioned on a{" "}
            <em>specific real person&apos;s</em> past answers, meant to predict that individual.{" "}
            <Ext href="https://arxiv.org/abs/2505.17479">Twin-2K-500</Ext> (Toubia et al., 2025) is
            the landmark dataset here.
          </li>
        </Ul>

        <H2>What the evidence says they can do</H2>
        <P>
          The replication record is stronger than skeptics expect. On the Twin-2K-500 battery of 17
          classic heuristics-and-biases experiments, our ensemble of off-the-shelf models{" "}
          <Link
            href="/research"
            className="text-blue-700 hover:text-blue-800 underline underline-offset-2"
          >
            reproduced 15.5 of 17 known human effects (~91%)
          </Link>
          {" "}— framing, anchoring, conjunction fallacy, sunk cost, and more (see the{" "}
          <Link
            href="/biases"
            className="text-blue-700 hover:text-blue-800 underline underline-offset-2"
          >
            bias-by-bias breakdown
          </Link>
          ). Economists have found
          LLMs reproducing classic results as{" "}
          <Ext href="https://www.nber.org/papers/w31122">simulated economic agents</Ext> (Horton,
          2023). The pattern across studies: well-established, robust human effects usually
          re-emerge in AI respondents.
        </P>

        <H2>What they reliably get wrong</H2>
        <Ul>
          <li>
            <strong>They can be too rational.</strong> Effects that depend on people missing
            something (like a masked dominant option) often fail to reproduce — the model spots the
            trick.
          </li>
          <li>
            <strong>Variance is too small.</strong> AI respondents tend to agree with each other
            more than humans do, which inflates apparent power and shrinks realistic noise.
          </li>
          <li>
            <strong>Individual-level prediction is hard.</strong> Even twins conditioned on a
            person&apos;s own past answers reproduce only about half of expected effects. Predicting{" "}
            <em>a specific person</em> is a much harder problem than reproducing{" "}
            <em>population-level effects</em>.
          </li>
          <li>
            <strong>Novel or culture-bound effects are uncertain.</strong> The benchmark record is
            built on classic paradigms; an effect unlike anything in the literature is exactly where
            an AI result deserves the least trust.
          </li>
        </Ul>

        <H2>The honest use case: pretesting, not replacing</H2>
        <P>
          Used as a <em>replacement</em> for human data, synthetic respondents will eventually burn
          you — a hit isn&apos;t proof and a null isn&apos;t a verdict. Used as a{" "}
          <em>pretest</em>, they&apos;re the best new tool in years: for a few dollars you learn
          whether your manipulation moves anything, whether your logic and wording survive contact
          with a reader, and whether your effect shows signs of life — before you spend hundreds on
          participants. Field the studies that pass; fix or rethink the ones that don&apos;t.
        </P>
        <P>
          That&apos;s the philosophy Doppelganger is built on: run your actual Qualtrics survey
          through AI respondents first, then spend your participant budget where it counts.
        </P>
      </>
    ),
  },
  {
    slug: "what-does-a-survey-study-cost",
    title: "What a behavioral study really costs — and where the money gets wasted",
    description:
      "A realistic budget for fielding a survey experiment on Prolific or MTurk in 2026, the hidden multipliers researchers forget, and the cheapest ways to stop paying for broken studies.",
    date: "2026-10-15",
    readMinutes: 5,
    Body: () => (
      <>
        <P>
          Every researcher eventually does this math on a napkin, so let&apos;s do it properly. The
          headline: a single well-powered, two-condition online experiment routinely costs{" "}
          <strong>several hundred to a few thousand dollars</strong> — and the most common way to
          waste that money has nothing to do with the platform you choose.
        </P>

        <H2>The core arithmetic</H2>
        <P>
          Participant cost is <em>(minutes &times; hourly rate &times; N) + platform fees</em>. A
          worked example: a 10-minute study paying a fair $12/hour is $2 per participant. Power a
          medium effect (d &asymp; 0.5) at 80% in a two-group design and you need roughly 64 per
          condition — call it 130 people with a little buffer. That&apos;s $260 in payments, plus
          platform fees (typically 25&ndash;40% on top across Prolific, MTurk with a requester fee,
          or CloudResearch) — roughly <strong>$325&ndash;$365 all-in</strong>.
        </P>
        <P>
          Now the sobering version: halve the effect size (d &asymp; 0.25 — common for subtle
          manipulations) and you need ~250 per condition. The same study is now{" "}
          <strong>$1,250&ndash;$1,400</strong>. Add a third condition, a longer instrument, or a
          specialized sample (parents, clinicians, a specific nationality) and multi-thousand-dollar
          studies arrive fast.
        </P>

        <H2>The hidden multipliers</H2>
        <Ul>
          <li>
            <strong>Exclusions.</strong> Attention-check failures, speeders, and duplicate IPs
            commonly eat 5&ndash;15% of a sample. You pay for those responses anyway.
          </li>
          <li>
            <strong>Re-fielding.</strong> The silent budget killer. A broken branch, a reversed
            scale, a manipulation that didn&apos;t land — and the whole run is dead. Nobody budgets
            for running the study twice, yet it happens constantly.
          </li>
          <li>
            <strong>Pilots.</strong> A proper human pilot of 30&ndash;50 people is another
            $75&ndash;$150 per iteration — and wording usually takes more than one iteration.
          </li>
        </Ul>

        <H2>Where the waste actually is</H2>
        <P>
          Platform fees get the grumbling, but the real waste is <strong>paying full price to
          discover your study was broken</strong>. Every dollar spent collecting data from a survey
          with a dead manipulation or corrupted skip logic is a dollar that bought you nothing but
          the bad news. The cheapest money you will ever spend on a study is whatever it costs to
          find those problems <em>before</em> N = 500 sees it.
        </P>

        <H2>The cheap insurance stack</H2>
        <Ul>
          <li>
            <strong>Free:</strong> preview the survey yourself; run Qualtrics&apos;s built-in test
            responses to verify the data pipeline.
          </li>
          <li>
            <strong>A few dollars:</strong> run AI respondents through the real survey — actual
            randomizer, actual branching — to check the manipulation moves, the wording survives a
            reader, and the effect shows signs of life. (This is what Doppelganger does.)
          </li>
          <li>
            <strong>A hundred dollars:</strong> a small human pilot for the things only people can
            tell you — timing, fatigue, open-text quality.
          </li>
          <li>
            <strong>The real spend:</strong> field the full sample once, on a study you already
            know works.
          </li>
        </Ul>
        <P>
          For the sample-size math behind these numbers, see our{" "}
          <Link
            href="/blog/how-many-participants-do-i-need"
            className="text-blue-700 hover:text-blue-800 underline underline-offset-2"
          >
            power-analysis primer
          </Link>{" "}
          — or plug your own study into the free{" "}
          <Link
            href="/sample-size-calculator"
            className="text-blue-700 hover:text-blue-800 underline underline-offset-2"
          >
            sample size &amp; cost calculator
          </Link>
          .
        </P>
      </>
    ),
  },
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
          anchoring, sunk-cost, and more. We ran all 17 studies through an ensemble of AI
          respondents — several models, counting an effect as reproduced when any of them shows it —
          and tallied how many of these well-established human effects it reproduced.
        </P>

        <H2>The result</H2>
        <P>
          Our ensemble reproduced <strong>15.5 of the 17 effects (about 91%)</strong>. For
          comparison, the AI &ldquo;digital twins&rdquo; built in the original study — models
          conditioned on each real person&apos;s prior answers — reproduced 9. On the same studies,
          scored the same way, our respondents matched <em>far more</em> of the known human effects.
          (The half-point is the endowment effect, which reproduces only partially.)
        </P>
        <P>
          The practical read: <strong>if your effect is real, there&apos;s roughly a 90% chance
          it will show up in AI respondents too.</strong> That makes an AI pretest a strong early
          signal about whether an idea is worth fielding.
        </P>

        <H2>What it does <em>not</em> mean</H2>
        <P>We think the honest framing matters more than the headline, so here are the limits:</P>
        <Ul>
          <li>
            <strong>It is not a replacement for human data.</strong> Even across the ensemble, one
            of the 17 effects (dominance neglect) didn&apos;t reproduce and one more (the endowment
            effect) only partially — AI respondents can still be too rational and miss some biases.
            Any single model reproduces fewer effects than the ensemble does.
          </li>
          <li>
            <strong>A null isn&apos;t a death sentence, and a hit isn&apos;t proof.</strong> Use the
            pretest to prioritize and de-risk — not to make the final call.
          </li>
          <li>
            <strong>Text and images, for now.</strong> Our respondents read written questions and
            see image stimuli; they can&apos;t yet watch video or listen to audio.
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
          commit to a power analysis at all. Try our free{" "}
          <Link
            href="/sample-size-calculator"
            className="text-blue-700 hover:text-blue-800 underline underline-offset-2"
          >
            sample size calculator
          </Link>{" "}
          for the common two-condition case (with a fielding-cost estimate), use{" "}
          <Ext href="https://www.gpower.hhu.de/">G*Power</Ext> for complex designs, and use a
          pretest to make sure the thing you&apos;re powering for is actually there.
        </P>
      </>
    ),
  },
];

export function getPost(slug: string): Post | undefined {
  return POSTS.find((p) => p.slug === slug);
}
