"use client";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";

const PACKS = [
  { id: "starter",  credits: 50,  price: "$9.99",  per: "$0.20", label: "Starter" },
  { id: "standard", credits: 100, price: "$17.99", per: "$0.18", label: "Standard", popular: true },
  { id: "pro",      credits: 250, price: "$39.99", per: "$0.16", label: "Pro" },
  { id: "research", credits: 500, price: "$69.99", per: "$0.14", label: "Research" },
];

// Team-background affiliations (honest "built by", NOT customer endorsements).
// Drop the matching SVG/PNG files into web/frontend/public/logos/.
const TEAM_FROM = [
  { name: "UT Austin McCombs", src: "/logos/ut-austin.png" },
  { name: "Chicago Booth",     src: "/logos/uchicago.png" },
  { name: "Northwestern",      src: "/logos/northwestern.jpeg" },
  { name: "Wisconsin",         src: "/logos/wisconsin.png" },
];

export default function Home() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [authed, setAuthed] = useState(false);

  // If the visitor already has a valid session (e.g. clicked the magic link
  // earlier), surface a "Go to dashboard" path so they're never stranded on the
  // marketing page thinking they're locked out.
  useEffect(() => {
    api.me().then(() => setAuthed(true)).catch(() => setAuthed(false));
  }, []);

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
        <span className="font-bold text-lg tracking-tight">Doppelganger</span>
        {authed
          ? <a href="/dashboard" className="text-sm font-medium text-blue-700 hover:text-blue-800">Go to dashboard →</a>
          : <a href="#login" className="text-sm font-medium text-blue-700 hover:text-blue-800">Sign in →</a>}
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
          Free to try · No credit card · Results in minutes
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

      {/* What you can test */}
      <section className="bg-slate-50 border-y border-slate-200">
        <div className="max-w-5xl mx-auto px-6 py-20">
          <h2 className="font-serif text-3xl font-bold text-center mb-3 text-slate-900">What you can pretest today</h2>
          <p className="text-center text-slate-600 mb-12 max-w-2xl mx-auto leading-relaxed">
            If your survey is text-based, you can run it through Doppelganger right now. Our AI
            respondents read and answer written questions — they can&apos;t yet see images or watch video.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            {/* Works today */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
              <h3 className="font-semibold text-lg mb-5 text-slate-900">Works today</h3>
              <ul className="space-y-3">
                {[
                  "Multiple choice & checkboxes",
                  "Likert scales & matrix / grid questions",
                  "Open-ended text responses",
                  "Demographic & screening questions",
                  "Branching, skip logic & randomized conditions",
                ].map((item) => (
                  <li key={item} className="flex items-start gap-3 text-sm text-slate-700">
                    <span className="text-green-600 font-bold mt-0.5">✓</span>
                    <span>{item}</span>
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
                  "Image stimuli (e.g. rating an ad or product photo)",
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
                We&apos;re building multimodal pretesting — soon your AI respondents will see images
                and watch video too.
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
            Buy credits up front · 1 credit = 1 AI respondent · A full pretest costs less than a single MTurk pilot.
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
                <a
                  href="#login"
                  className={`mt-auto text-center py-2 rounded-lg font-medium text-sm transition ${
                    pack.popular
                      ? "bg-blue-700 hover:bg-blue-800 text-white"
                      : "bg-slate-100 hover:bg-slate-200 text-slate-800"
                  }`}
                >
                  Buy {pack.label}
                </a>
              </div>
            ))}
          </div>
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
          <h2 className="font-serif text-2xl font-bold mb-2 text-slate-900">Start pretesting</h2>
          <p className="text-slate-600 text-sm mb-6">No password — we&apos;ll email you a secure sign-in link.</p>
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

      <footer className="border-t border-slate-200 text-center text-slate-500 text-sm py-8">
        © {new Date().getFullYear()} Doppelganger · A survey pretesting tool · Not affiliated with Qualtrics or Google
      </footer>
    </main>
  );
}
