"use client";
import { useState } from "react";
import { api } from "@/lib/api";

const PACKS = [
  { id: "starter",  credits: 50,  price: "$9.99",  per: "$0.20", label: "Starter" },
  { id: "standard", credits: 100, price: "$17.99", per: "$0.18", label: "Standard", popular: true },
  { id: "pro",      credits: 250, price: "$39.99", per: "$0.16", label: "Pro" },
  { id: "research", credits: 500, price: "$69.99", per: "$0.14", label: "Research" },
];

export default function Home() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

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
    <main className="min-h-screen bg-gray-950 text-white">
      {/* Nav */}
      <nav className="border-b border-gray-800 px-6 py-4 flex items-center justify-between max-w-6xl mx-auto">
        <span className="font-bold text-lg tracking-tight">Doppelganger</span>
        <a href="#login" className="text-sm text-blue-400 hover:text-blue-300">Sign in →</a>
      </nav>

      {/* Hero */}
      <section className="max-w-3xl mx-auto px-6 pt-24 pb-16 text-center">
        <h1 className="text-5xl font-bold leading-tight mb-6">
          Test your idea with<br />an AI audience first
        </h1>
        <p className="text-xl text-gray-400 mb-10">
          Run your survey through hundreds of AI personas in minutes.
          Get realistic, condition-aware responses — before you spend on real participants.
        </p>
        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <a href="#login" className="bg-blue-600 hover:bg-blue-500 text-white font-semibold px-8 py-3 rounded-lg transition">
            Get started free
          </a>
          <a href="#how" className="border border-gray-700 hover:border-gray-500 text-gray-300 px-8 py-3 rounded-lg transition">
            How it works
          </a>
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="max-w-5xl mx-auto px-6 py-16">
        <h2 className="text-3xl font-bold text-center mb-12">How it works</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-8">
          {[
            { n: "1", title: "Paste your survey URL", desc: "Drop in your Qualtrics survey link. We auto-convert it to an AI-compatible version in seconds." },
            { n: "2", title: "Choose participants", desc: "Pick how many AI personas to run (1–1000). Smoke test with 5 first to verify everything looks right." },
            { n: "3", title: "Download results", desc: "Results land directly in your Qualtrics Data & Analysis tab. Download a CSV from here too." },
          ].map((step) => (
            <div key={step.n} className="bg-gray-900 rounded-xl p-6 border border-gray-800">
              <div className="text-blue-400 font-bold text-2xl mb-3">{step.n}</div>
              <h3 className="font-semibold text-lg mb-2">{step.title}</h3>
              <p className="text-gray-400 text-sm leading-relaxed">{step.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="max-w-5xl mx-auto px-6 py-16">
        <h2 className="text-3xl font-bold text-center mb-4">Simple, per-participant pricing</h2>
        <p className="text-center text-gray-400 mb-12">Buy credits upfront. 1 credit = 1 simulated participant.</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {PACKS.map((pack) => (
            <div
              key={pack.id}
              className={`rounded-xl border p-6 flex flex-col ${
                pack.popular
                  ? "border-blue-500 bg-blue-950"
                  : "border-gray-800 bg-gray-900"
              }`}
            >
              {pack.popular && (
                <span className="text-blue-400 text-xs font-semibold uppercase tracking-wider mb-3">
                  Most popular
                </span>
              )}
              <div className="text-2xl font-bold mb-1">{pack.price}</div>
              <div className="text-gray-400 text-sm mb-4">{pack.credits} participants · {pack.per} each</div>
              <div className="font-semibold text-lg mb-6">{pack.label}</div>
              <a
                href="#login"
                className={`mt-auto text-center py-2 rounded-lg font-medium text-sm transition ${
                  pack.popular
                    ? "bg-blue-600 hover:bg-blue-500 text-white"
                    : "bg-gray-800 hover:bg-gray-700 text-gray-200"
                }`}
              >
                Buy {pack.label}
              </a>
            </div>
          ))}
        </div>
      </section>

      {/* Login */}
      <section id="login" className="max-w-md mx-auto px-6 py-16">
        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-8">
          <h2 className="text-2xl font-bold mb-2">Sign in</h2>
          <p className="text-gray-400 text-sm mb-6">No password needed — we&apos;ll email you a link.</p>
          {sent ? (
            <div className="text-green-400 font-medium">
              ✓ Check your email for a magic link!
            </div>
          ) : (
            <form onSubmit={handleLogin} className="flex flex-col gap-4">
              <input
                type="email"
                placeholder="you@university.edu"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
              />
              {error && <p className="text-red-400 text-sm">{error}</p>}
              <button
                type="submit"
                disabled={loading}
                className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-semibold py-3 rounded-lg transition"
              >
                {loading ? "Sending…" : "Send magic link"}
              </button>
            </form>
          )}
        </div>
      </section>

      <footer className="border-t border-gray-800 text-center text-gray-600 text-sm py-8">
        © {new Date().getFullYear()} Doppelganger · Not affiliated with Qualtrics or Google
      </footer>
    </main>
  );
}
