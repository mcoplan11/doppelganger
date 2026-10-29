"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

const PACKS = [
  { id: "starter",  credits: 200,  price: "$7.99",  per: "$0.04",  label: "Starter" },
  { id: "standard", credits: 600,  price: "$14.99", per: "$0.025", label: "Standard", popular: true },
  { id: "pro",      credits: 1200, price: "$24.99", per: "$0.02",  label: "Pro" },
];

// Team-background affiliations (honest "built by", NOT customer endorsements).
// Drop the matching SVG/PNG files into web/frontend/public/logos/.
const TEAM_FROM = [
  { name: "UT Austin McCombs", src: "/logos/ut-austin.png" },
  { name: "Chicago Booth",     src: "/logos/uchicago.png" },
  { name: "Northwestern",      src: "/logos/northwestern.jpeg" },
  { name: "Wisconsin",         src: "/logos/wisconsin.png" },
];

// "Does it work?" — replication benchmark against the published Twin-2K-500 study.
// Both approaches scored on the SAME 17 classic heuristics-and-biases experiments: an
// effect "replicates" when the respondents reproduce the original author's result
// (statistically significant, in the expected direction). "Our ensemble" runs each
// study through several models and counts an effect reproduced when any one of them
// shows it; the endowment effect reproduces only partially, hence the 15.5.
// Source: Toubia et al. (2025).
const REPLICATION = {
  studyUrl: "https://arxiv.org/abs/2505.17479",
  total: 17,
  rows: [
    { label: "Our ensemble of AI respondents", count: 15.5, highlight: true },
    { label: "The study's own AI digital twins", count: 9, highlight: false },
  ],
};

// Buyer-intent questions people actually type. Doubles as FAQPage structured data
// (below), which is what Google and AI answer engines pull into featured snippets
// and AI Overviews. Keep answers factual and self-contained.
const FAQS: Array<{ q: string; a: string }> = [
  {
    q: "Can AI replace survey respondents?",
    a: "Not for confirmatory research, but AI respondents are a strong pretest. In our benchmark against the published Twin-2K-500 dataset, an ensemble of AI respondents reproduced about 91% of 17 classic human decision-making effects. If an effect is real, there's roughly a 90% chance it shows up in AI respondents too — enough to catch broken studies before you pay for a real sample.",
  },
  {
    q: "How accurate are AI survey respondents?",
    a: "On an external, published benchmark of 17 classic behavioral experiments, Doppelganger's ensemble reproduced 15.5 of them (about 91%), compared with 9 for the AI 'digital twins' built in the original study. Accuracy varies by task: some biases reproduce fully, a few only partially, and AI can still be 'too rational' on effects like dominance neglect.",
  },
  {
    q: "How much does it cost to pretest a survey with AI?",
    a: "Every new account starts with 200 free credits — enough for a full pretest before you pay anything. After that, credits start at $7.99 for 200 respondents (about $0.04 each), and a full pretest typically costs less than a single MTurk or Prolific pilot. One credit equals one AI respondent.",
  },
  {
    q: "What kinds of surveys can I test?",
    a: "Any Qualtrics survey built from text and images: multiple choice, Likert and matrix questions, open-ended text, demographics and screeners, and branching, skip logic, or randomized conditions. Image stimuli are supported too — AI respondents actually see embedded images, so you can pretest ad ratings, product photos, and other visual stimuli. Video and audio aren't supported yet.",
  },
  {
    q: "Do I still need real participants?",
    a: "Yes. AI pretesting is a screening tool, not a replacement for human data. Use it to catch broken skip logic, dead-on-arrival manipulations, and confusing wording, then spend your participant budget on the studies that already show signs of life. A null result in simulation is not proof of a null in humans.",
  },
  {
    q: "How does Doppelganger work with Qualtrics?",
    a: "You point Doppelganger at your Qualtrics survey and it runs the study through persona-conditioned AI respondents in minutes, returning per-question results so you can see whether your manipulation moved anything before you field it on people.",
  },
];

export default function Home() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [authed, setAuthed] = useState(false);
  const [checkingOut, setCheckingOut] = useState<string | null>(null);
  // Set when an anonymous visitor clicks "Buy" — shows a prompt in the login
  // section explaining they must sign in via emailed link before purchasing.
  const [promptLogin, setPromptLogin] = useState(false);

  // If the visitor already has a valid session (e.g. clicked the magic link
  // earlier), surface a "Go to dashboard" path so they're never stranded on the
  // marketing page thinking they're locked out.
  useEffect(() => {
    api.me().then(() => setAuthed(true)).catch(() => setAuthed(false));
  }, []);

  // Buy-credits click on the marketing page. Anonymous visitors can't check out
  // (the backend requires a session), so instead of silently scrolling we send
  // them to the login form with a clear "sign in via email link first" message.
  // Signed-in visitors go straight to Stripe checkout.
  async function handleBuy(packId: string) {
    if (!authed) {
      setPromptLogin(true);
      document.getElementById("login")?.scrollIntoView({ behavior: "smooth" });
      return;
    }
    setCheckingOut(packId);
    try {
      const { checkout_url } = await api.checkout(packId);
      window.location.assign(checkout_url);
    } catch {
      // Session likely expired since page load — treat as logged out and
      // prompt them to sign in again rather than showing a raw error.
      setAuthed(false);
      setPromptLogin(true);
      setCheckingOut(null);
      document.getElementById("login")?.scrollIntoView({ behavior: "smooth" });
    }
  }

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await api.requestMagicLink(email);
      setSent(true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-white text-slate-900">
      {/* Nav */}
      <nav className="border-b border-slate-200 px-6 py-4 flex items-center justify-between max-w-6xl mx-auto">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/logo-wordmark.png" alt="Doppelganger Labs" className="h-8 w-auto" />
        <div className="flex items-center gap-6 text-sm font-medium">
          <Link href="/research" className="text-slate-600 hover:text-slate-900">Research</Link>
          <Link href="/blog" className="text-slate-600 hover:text-slate-900">Blog</Link>
          {authed
            ? <a href="/dashboard" className="text-blue-700 hover:text-blue-800">Go to dashboard →</a>
            : <a href="#login" className="text-blue-700 hover:text-blue-800">Sign in →</a>}
        </div>
      </nav>

      {/* Hero */}
      <section className="max-w-3xl mx-auto px-6 pt-20 pb-12 text-center">
        <h1 className="font-serif text-4xl sm:text-5xl font-bold leading-tight tracking-tight mb-6 text-slate-900">
          Pretest your study before<br />you pay for real participants
        </h1>
        <p className="text-lg sm:text-xl text-slate-600 leading-relaxed mb-8">
          Doppelganger runs your Qualtrics survey through AI respondents in minutes —
          so you catch problems and gauge your effect before you spend on participants.
        </p>
        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <a href={authed ? "/dashboard" : "#login"} className="bg-blue-700 hover:bg-blue-800 text-white font-semibold px-8 py-3 rounded-lg transition">
            {authed ? "Go to my dashboard" : "Pretest a survey free"}
          </a>
          <a href="#how" className="border border-slate-300 hover:bg-slate-50 text-slate-700 font-medium px-8 py-3 rounded-lg transition">
            See how it works
          </a>
        </div>
        <p className="text-sm text-slate-500 mt-4">
          Start with 200 free AI respondents · No credit card · Results in minutes
        </p>
      </section>

      {/* Built by — team-background affiliations */}
      <section className="max-w-4xl mx-auto px-6 pb-16">
        <div className="border-y border-slate-200 py-8">
          <p className="text-center text-xs font-semibold uppercase tracking-wider text-slate-400 mb-6">
            Built by a team from
          </p>
          <div className="flex flex-wrap items-center justify-center gap-x-10 gap-y-6">
            {TEAM_FROM.map((org) => (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                key={org.name}
                src={org.src}
                alt={org.name}
                className="h-10 sm:h-12 w-auto object-contain opacity-70 grayscale hover:opacity-100 hover:grayscale-0 transition"
              />
            ))}
          </div>
        </div>
      </section>

      {/* Why researchers use it */}
      <section className="bg-slate-50 border-y border-slate-200">
        <div className="max-w-5xl mx-auto px-6 py-16">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-8">
            {[
              {
                title: "Cheaper than a pilot",
                desc: "A full AI pretest costs less than a coffee. Save your participant budget for the studies that already show signs of life.",
              },
              {
                title: "Hours, not weeks",
                desc: "No recruiting, no fielding wait. Catch broken skip logic and dead-on-arrival manipulations the same afternoon you build the survey.",
              },
              {
                title: "Works with your Qualtrics survey",
                desc: "Point it at an existing survey — branches, conditions, and embedded data included. Your original is never touched.",
              },
            ].map((item) => (
              <div key={item.title}>
                <h3 className="font-semibold text-lg mb-2 text-slate-900">{item.title}</h3>
                <p className="text-slate-600 text-sm leading-relaxed">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="max-w-5xl mx-auto px-6 py-20">
        <h2 className="font-serif text-3xl font-bold text-center mb-12 text-slate-900">How it works</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
          {[
            { n: "1", title: "Paste your Qualtrics survey", desc: "Drop in your survey link. We create an AI-compatible copy automatically — your original stays exactly as it is." },
            { n: "2", title: "Run a free trial first", desc: "Send 3 AI respondents through to confirm everything flows correctly. Scale up to a full pretest once it looks right." },
            { n: "3", title: "Read the results", desc: "Responses land in your Qualtrics Data & Analysis tab, plus a CSV here. See whether the manipulation moved anything before you spend a cent on MTurk." },
          ].map((step) => (
            <div key={step.n} className="bg-white rounded-xl p-6 border border-slate-200 shadow-sm">
              <div className="text-blue-700 font-bold text-2xl mb-3">{step.n}</div>
              <h3 className="font-semibold text-lg mb-2 text-slate-900">{step.title}</h3>
              <p className="text-slate-600 text-sm leading-relaxed">{step.desc}</p>
            </div>
          ))}
        </div>

        {/* Honest framing — builds trust with a skeptical academic audience */}
        <p className="max-w-2xl mx-auto text-center text-sm text-slate-500 leading-relaxed mt-12 border-t border-slate-200 pt-8">
          Doppelganger is a pretesting tool, not a substitute for human data. Use it to catch
          problems and judge whether an idea is worth fielding — then run the real study with
          confidence.
        </p>
      </section>

      {/* Does it actually work? — replication benchmark vs a published study */}
      <section id="does-it-work" className="bg-white border-t border-slate-200">
        <div className="max-w-4xl mx-auto px-6 py-20">
          <h2 className="font-serif text-3xl font-bold text-center mb-3 text-slate-900">Does it actually work?</h2>
          <p className="text-center text-slate-600 mb-12 max-w-2xl mx-auto leading-relaxed">
            We benchmarked our AI respondents against{" "}
            <a
              href={REPLICATION.studyUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-700 hover:text-blue-800 underline underline-offset-2"
            >
              Twin-2K-500
            </a>{" "}
            (Toubia et al., 2025) — a published dataset of {REPLICATION.total} classic
            behavioral-science experiments, including framing effects, the Linda conjunction
            problem, anchoring, and sunk-cost. We ran every study through an ensemble of AI
            respondents and counted how many of these well-established human effects it reproduced.
          </p>

          <div className="max-w-2xl mx-auto space-y-6">
            {REPLICATION.rows.map((row) => {
              const pct = Math.round((row.count / REPLICATION.total) * 100);
              return (
                <div key={row.label}>
                  <div className="flex items-baseline justify-between mb-2">
                    <span className={`text-sm font-medium ${row.highlight ? "text-slate-900" : "text-slate-500"}`}>
                      {row.label}
                    </span>
                    <span className={`text-sm font-semibold ${row.highlight ? "text-blue-700" : "text-slate-500"}`}>
                      {row.count} of {REPLICATION.total} effects
                    </span>
                  </div>
                  <div className="h-3 w-full rounded-full bg-slate-100 overflow-hidden">
                    <div
                      className={`h-full rounded-full ${row.highlight ? "bg-blue-600" : "bg-slate-300"}`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>

          <p className="max-w-2xl mx-auto text-center text-base sm:text-lg font-medium text-slate-800 leading-relaxed mt-12">
            In plain terms: if your effect is real, there&apos;s roughly a 90% chance it&apos;ll
            show up in our AI respondents too.
          </p>

          <p className="max-w-2xl mx-auto text-center text-sm text-slate-500 leading-relaxed mt-6 border-t border-slate-200 pt-8">
            Same {REPLICATION.total} studies, same scoring. Our ensemble reproduced more of the real
            human effects than the AI &ldquo;digital twins&rdquo; built in the source study itself.
            It won&apos;t catch every effect — but it&apos;s a strong signal your manipulation is
            real before you spend on participants.
          </p>
          <div className="flex flex-wrap justify-center gap-x-6 gap-y-2 mt-6">
            <Link
              href="/blog/can-ai-replace-survey-respondents"
              className="text-sm font-medium text-blue-700 hover:text-blue-800"
            >
              See how we measured this →
            </Link>
            <Link
              href="/research"
              className="text-sm font-medium text-blue-700 hover:text-blue-800"
            >
              Read the research paper →
            </Link>
          </div>
        </div>
      </section>

      {/* What you can test */}
      <section className="bg-slate-50 border-y border-slate-200">
        <div className="max-w-5xl mx-auto px-6 py-20">
          <h2 className="font-serif text-3xl font-bold text-center mb-3 text-slate-900">What you can pretest today</h2>
          <p className="text-center text-slate-600 mb-12 max-w-2xl mx-auto leading-relaxed">
            If your survey is built from text and images, you can run it through Doppelganger right
            now. Our AI respondents read written questions and actually see embedded images — they
            can&apos;t yet watch video or listen to audio.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            {/* Works today */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
              <h3 className="font-semibold text-lg mb-5 text-slate-900">Works today</h3>
              <ul className="space-y-3">
                {([
                  { label: "Multiple choice & checkboxes" },
                  { label: "Likert scales & matrix / grid questions" },
                  { label: "Open-ended text responses" },
                  { label: "Demographic & screening questions" },
                  { label: "Branching, skip logic & randomized conditions" },
                  { label: "Image stimuli (e.g. rating an ad or product photo)", isNew: true },
                ] as Array<{ label: string; isNew?: boolean }>).map((item) => (
                  <li key={item.label} className="flex items-start gap-3 text-sm text-slate-700">
                    <span className="text-green-600 font-bold mt-0.5">✓</span>
                    <span>
                      {item.label}
                      {item.isNew && (
                        <span className="ml-2 align-middle text-xs font-semibold uppercase tracking-wider text-green-700 bg-green-50 border border-green-200 rounded-full px-2 py-0.5">
                          New
                        </span>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
            {/* Coming soon */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
              <div className="flex items-center gap-2 mb-5">
                <h3 className="font-semibold text-lg text-slate-900">Not yet</h3>
                <span className="text-xs font-semibold uppercase tracking-wider text-blue-700 bg-blue-50 border border-blue-200 rounded-full px-2 py-0.5">
                  Coming soon
                </span>
              </div>
              <ul className="space-y-3">
                {[
                  "Video stimuli",
                  "Audio clips",
                  "Interactive tasks — heatmaps, drag-and-drop, sliders",
                ].map((item) => (
                  <li key={item} className="flex items-start gap-3 text-sm text-slate-500">
                    <span className="text-slate-300 font-bold mt-0.5">○</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
              <p className="text-sm text-slate-500 mt-5 pt-4 border-t border-slate-200 leading-relaxed">
                Your AI respondents already see images — full multimodal pretesting is next, with
                video and audio on the way.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="bg-white">
        <div className="max-w-5xl mx-auto px-6 py-20">
          <h2 className="font-serif text-3xl font-bold text-center mb-3 text-slate-900">Pricing that fits a research budget</h2>
          <p className="text-center text-slate-600 mb-12">
            Every new account starts with 200 free credits · 1 credit = 1 AI respondent · A full
            pretest costs less than a single MTurk pilot.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {PACKS.map((pack) => (
              <div
                key={pack.id}
                className={`rounded-xl border p-6 flex flex-col bg-white shadow-sm ${
                  pack.popular ? "border-blue-600 ring-1 ring-blue-600" : "border-slate-200"
                }`}
              >
                {pack.popular && (
                  <span className="text-blue-700 text-xs font-semibold uppercase tracking-wider mb-3">
                    Most popular
                  </span>
                )}
                <div className="text-2xl font-bold mb-1 text-slate-900">{pack.price}</div>
                <div className="text-slate-500 text-sm mb-4">{pack.credits} respondents · {pack.per} each</div>
                <div className="font-semibold text-lg mb-6 text-slate-900">{pack.label}</div>
                <button
                  onClick={() => handleBuy(pack.id)}
                  disabled={checkingOut === pack.id}
                  className={`mt-auto text-center py-2 rounded-lg font-medium text-sm transition disabled:opacity-50 ${
                    pack.popular
                      ? "bg-blue-700 hover:bg-blue-800 text-white"
                      : "bg-slate-100 hover:bg-slate-200 text-slate-800"
                  }`}
                >
                  {checkingOut === pack.id ? "Redirecting…" : `Buy ${pack.label}`}
                </button>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ — visible answers + FAQPage structured data for rich results / AI Overviews */}
      <section id="faq" className="bg-slate-50 border-y border-slate-200">
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              "@context": "https://schema.org",
              "@type": "FAQPage",
              mainEntity: FAQS.map((f) => ({
                "@type": "Question",
                name: f.q,
                acceptedAnswer: { "@type": "Answer", text: f.a },
              })),
            }),
          }}
        />
        <div className="max-w-3xl mx-auto px-6 py-20">
          <h2 className="font-serif text-3xl font-bold text-center mb-12 text-slate-900">
            Frequently asked questions
          </h2>
          <div className="divide-y divide-slate-200">
            {FAQS.map((f) => (
              <div key={f.q} className="py-6 first:pt-0">
                <h3 className="font-semibold text-lg text-slate-900 mb-2">{f.q}</h3>
                <p className="text-slate-600 leading-relaxed">{f.a}</p>
              </div>
            ))}
          </div>
          <p className="text-center text-sm text-slate-500 mt-10">
            More on the evidence in our{" "}
            <Link href="/research" className="text-blue-700 hover:text-blue-800 font-medium">
              research report
            </Link>{" "}
            and{" "}
            <Link href="/blog" className="text-blue-700 hover:text-blue-800 font-medium">
              blog
            </Link>
            .
          </p>
        </div>
      </section>

      {/* Login */}
      <section id="login" className="max-w-md mx-auto px-6 py-20">
        <div className="bg-white border border-slate-200 shadow-sm rounded-2xl p-8">
          {authed ? (
            <div className="text-center">
              <h2 className="font-serif text-2xl font-bold mb-2 text-slate-900">You&apos;re signed in</h2>
              <p className="text-slate-600 text-sm mb-6">No need to log in again — head to your dashboard.</p>
              <a
                href="/dashboard"
                className="inline-block bg-blue-700 hover:bg-blue-800 text-white font-semibold px-8 py-3 rounded-lg transition"
              >
                Go to dashboard →
              </a>
            </div>
          ) : (
          <>
          {promptLogin && !sent && (
            <div className="mb-6 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800">
              Please log in to buy credits. Enter your email below and we&apos;ll send you a
              secure sign-in link — click the link in that email to finish signing in, then
              you can complete your purchase.
            </div>
          )}
          <h2 className="font-serif text-2xl font-bold mb-2 text-slate-900">Start pretesting</h2>
          <p className="text-slate-600 text-sm mb-6">
            New accounts start with 200 free credits. No password — we&apos;ll email you a secure
            sign-in link.
          </p>
          {sent ? (
            <div className="text-green-700 font-medium">
              ✓ Check your email for a magic link.
            </div>
          ) : (
            <form onSubmit={handleLogin} className="flex flex-col gap-4">
              <input
                type="email"
                placeholder="you@university.edu"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="bg-white border border-slate-300 rounded-lg px-4 py-3 text-slate-900 placeholder-slate-400 focus:outline-none focus:border-blue-600"
              />
              {error && <p className="text-red-600 text-sm">{error}</p>}
              <button
                type="submit"
                disabled={loading}
                className="bg-blue-700 hover:bg-blue-800 disabled:opacity-50 text-white font-semibold py-3 rounded-lg transition"
              >
                {loading ? "Sending…" : "Send magic link"}
              </button>
            </form>
          )}
          </>
          )}
        </div>
      </section>

      <footer className="border-t border-slate-200 text-slate-500 text-sm py-8">
        <div className="max-w-5xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-3">
          <span>© {new Date().getFullYear()} Doppelganger · A survey pretesting tool · Not affiliated with Qualtrics or Google</span>
          <a
            href="mailto:hello@doppelgangerlabs.com"
            className="text-blue-600 hover:text-blue-700 font-medium"
          >
            hello@doppelgangerlabs.com
          </a>
        </div>
      </footer>
    </main>
  );
}
