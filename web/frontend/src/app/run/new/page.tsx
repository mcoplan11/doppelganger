"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export default function NewRun() {
  const router = useRouter();
  const [form, setForm] = useState({
    survey_url: "",
    qualtrics_token: "",
    qualtrics_datacenter: "yul1",
    n_participants: 100,
    smoke_test: false,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [copyConsent, setCopyConsent] = useState(true);

  function set(field: string, value: string | number | boolean) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  async function submit(smoke: boolean) {
    setLoading(true);
    setError("");
    try {
      const run = await api.createRun({ ...form, smoke_test: smoke });
      router.push(`/run/${run.id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-gray-950 text-white">
      <nav className="border-b border-gray-800 px-6 py-4 flex items-center justify-between max-w-6xl mx-auto">
        <span className="font-bold text-lg tracking-tight">Doppelganger</span>
        <button onClick={() => router.push("/dashboard")} className="text-sm text-gray-400 hover:text-white">
          ← Dashboard
        </button>
      </nav>

      <div className="max-w-xl mx-auto px-6 py-12">
        <h1 className="text-2xl font-bold mb-2">New simulation</h1>
        <p className="text-gray-400 text-sm mb-8">
          We recommend running a <strong className="text-white">smoke test (5 participants)</strong> first to confirm your survey converts correctly — it&apos;s free.
        </p>

        <div className="flex flex-col gap-5">
          <Field label="Qualtrics survey URL or ID" hint="e.g. https://mccombs.qualtrics.com/jfe/form/SV_abc123 or just SV_abc123">
            <input
              type="text"
              placeholder="https://... or SV_..."
              value={form.survey_url}
              onChange={(e) => set("survey_url", e.target.value)}
              className="input"
            />
          </Field>

          <Field label="Qualtrics API token" hint="Found under Account Settings → Qualtrics IDs → API Token">
            <input
              type="password"
              placeholder="Your API token"
              value={form.qualtrics_token}
              onChange={(e) => set("qualtrics_token", e.target.value)}
              className="input"
            />
          </Field>

          <Field label="Datacenter ID" hint="Usually 'yul1' or 'fra1' — found in your Qualtrics URL">
            <input
              type="text"
              value={form.qualtrics_datacenter}
              onChange={(e) => set("qualtrics_datacenter", e.target.value)}
              className="input"
            />
          </Field>

          <Field label="Number of participants" hint="Full run size. Credits deducted per completed participant.">
            <input
              type="number"
              min={1}
              max={1000}
              value={form.n_participants}
              onChange={(e) => set("n_participants", parseInt(e.target.value) || 1)}
              className="input"
            />
          </Field>

          {/* AI copy disclosure */}
          <div className="bg-gray-900 border border-gray-700 rounded-xl p-4 text-sm">
            <p className="text-gray-300 font-medium mb-1">An AI-compatible survey copy will be created</p>
            <p className="text-gray-500 text-xs leading-relaxed mb-3">
              Some questions aren&apos;t compatible with AI respondents — sliders, CAPTCHAs, and redirect
              flows will be modified or removed. We create a separate copy of your survey (named
              &ldquo;[Your Survey Name] - AI Copy&rdquo;) so your original is never touched. The copy
              will appear in your Qualtrics account and can be deleted after the run.
            </p>
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={copyConsent}
                onChange={(e) => setCopyConsent(e.target.checked)}
                className="w-4 h-4 accent-blue-500"
              />
              <span className="text-gray-300 text-xs">
                I understand an AI copy of my survey will be created in my Qualtrics account
              </span>
            </label>
            {!copyConsent && (
              <p className="text-yellow-400 text-xs mt-2">
                The AI copy is required to run a simulation. Uncheck only if you don&apos;t want to proceed.
              </p>
            )}
          </div>

          {error && (
            <div className="bg-red-900/30 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">
              {error}
            </div>
          )}

          <div className="flex flex-col sm:flex-row gap-3 pt-2">
            <button
              onClick={() => submit(true)}
              disabled={loading || !form.survey_url || !form.qualtrics_token || !copyConsent}
              className="flex-1 border border-gray-700 hover:border-gray-500 disabled:opacity-40 text-gray-200 font-medium py-3 rounded-lg transition"
            >
              {loading ? "Starting…" : "Smoke test (5 participants, free)"}
            </button>
            <button
              onClick={() => submit(false)}
              disabled={loading || !form.survey_url || !form.qualtrics_token || !copyConsent}
              className="flex-1 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white font-semibold py-3 rounded-lg transition"
            >
              {loading ? "Starting…" : `Run ${form.n_participants} participants`}
            </button>
          </div>
        </div>
      </div>

      <style jsx>{`
        .input {
          width: 100%;
          background: rgb(17 24 39);
          border: 1px solid rgb(55 65 81);
          border-radius: 0.5rem;
          padding: 0.75rem 1rem;
          color: white;
          font-size: 0.875rem;
          outline: none;
          transition: border-color 0.15s;
        }
        .input:focus {
          border-color: rgb(59 130 246);
        }
        .input::placeholder {
          color: rgb(107 114 128);
        }
      `}</style>
    </main>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-300 mb-1">{label}</label>
      {children}
      {hint && <p className="text-gray-600 text-xs mt-1">{hint}</p>}
    </div>
  );
}
