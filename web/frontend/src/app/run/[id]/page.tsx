"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, type Run } from "@/lib/api";
import RunResults from "./RunResults";

const STATUS_LABELS: Record<string, string> = {
  converting: "Converting survey to AI-compatible copy…",
  running: "Simulation in progress…",
  done: "Completed",
  failed: "Failed",
  cancelled: "Cancelled",
};

const STATUS_COLORS: Record<string, string> = {
  converting: "text-yellow-400",
  running: "text-blue-400",
  done: "text-green-400",
  failed: "text-red-400",
  cancelled: "text-gray-400",
};

const STEPS = ["converting", "running", "done"];

export default function RunDetail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [run, setRun] = useState<Run | null>(null);
  const [cancelling, setCancelling] = useState(false);

  useEffect(() => {
    if (!id) return;
    api.getRun(parseInt(id)).then(setRun).catch(() => router.push("/dashboard"));
  }, [id, router]);

  // Poll while active
  useEffect(() => {
    if (!run || ["done", "failed"].includes(run.status)) return;
    const t = setTimeout(async () => {
      const updated = await api.getRun(run.id).catch(() => run);
      setRun(updated);
    }, 5000);
    return () => clearTimeout(t);
  }, [run]);

  if (!run) return <div className="min-h-screen bg-gray-950 flex items-center justify-center text-white">Loading…</div>;

  const currentStep = STEPS.indexOf(run.status);
  const isActive = !["done", "failed", "cancelled"].includes(run.status);

  async function handleCancel() {
    if (!run) return;
    if (!window.confirm("Are you sure you want to cancel this run? This cannot be undone.")) return;
    setCancelling(true);
    try {
      const updated = await api.cancelRun(run.id);
      setRun(updated);
    } finally {
      setCancelling(false);
    }
  }
  const color = STATUS_COLORS[run.status] ?? "text-gray-400";

  return (
    <main className="min-h-screen bg-gray-950 text-white">
      <nav className="border-b border-gray-800 px-6 py-4 flex items-center justify-between max-w-6xl mx-auto">
        <span className="font-bold text-lg tracking-tight">Doppelganger</span>
        <button onClick={() => router.push("/dashboard")} className="text-sm text-gray-400 hover:text-white">
          ← Dashboard
        </button>
      </nav>

      <div className="max-w-2xl mx-auto px-6 py-12">
        <div className="flex items-start justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold mb-1">
              {run.is_smoke_test ? "Trial run" : "Simulation"} #{run.id}
            </h1>
            <p className="text-gray-400 text-sm">{run.original_survey_id}</p>
          </div>
          <span className={`font-semibold ${color}`}>{run.status.charAt(0).toUpperCase() + run.status.slice(1)}</span>
        </div>

        {/* Progress steps */}
        <div className="flex items-center gap-2 mb-10">
          {STEPS.map((step, i) => {
            const done = currentStep > i || run.status === "done";
            const active = currentStep === i && isActive;
            return (
              <div key={step} className="flex items-center gap-2">
                <div className={`flex items-center justify-center w-7 h-7 rounded-full text-xs font-bold transition ${
                  done ? "bg-green-600 text-white" :
                  active ? "bg-blue-600 text-white animate-pulse" :
                  "bg-gray-800 text-gray-500"
                }`}>
                  {done ? "✓" : i + 1}
                </div>
                <span className={`text-xs hidden sm:inline ${active ? "text-white" : done ? "text-gray-300" : "text-gray-600"}`}>
                  {step.charAt(0).toUpperCase() + step.slice(1)}
                </span>
                {i < STEPS.length - 1 && <div className="w-8 h-px bg-gray-800" />}
              </div>
            );
          })}
          {run.status === "failed" && (
            <span className="text-red-400 text-xs ml-2">✕ Failed</span>
          )}
        </div>

        {/* Status message */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-6">
          <div className="text-gray-400 text-sm mb-4">
            {STATUS_LABELS[run.status] ?? run.status}
            {isActive && <span className="ml-1 animate-pulse">Auto-refreshing…</span>}
          </div>

          {run.status === "running" && (
            <div className="mb-4">
              <div className="flex justify-between text-xs text-gray-400 mb-1">
                <span>{run.credits_used} of {run.n_participants} completed</span>
                <span>{run.n_participants - run.credits_used} remaining</span>
              </div>
              <div className="w-full h-2 bg-gray-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-500 rounded-full transition-all duration-500"
                  style={{ width: run.n_participants > 0 ? `${(run.credits_used / run.n_participants) * 100}%` : "0%" }}
                />
              </div>
            </div>
          )}

          <div className="grid grid-cols-2 gap-4 text-sm">
            <Stat label="Participants" value={run.n_participants.toString()} />
            <Stat label="Credits used" value={run.credits_used.toString()} />
            <Stat label="Type" value={run.is_smoke_test ? "Trial run" : "Full run"} />
            {run.ai_survey_id && <Stat label="AI survey copy" value={run.ai_survey_id} />}
            {run.completed_at && (
              <Stat label="Completed" value={new Date(run.completed_at).toLocaleString()} />
            )}
            {run.completed_at && (
              <Stat label="Duration" value={formatDuration(run.created_at, run.completed_at)} />
            )}
          </div>

          {run.error && (
            <div className="mt-4 bg-red-900/30 border border-red-800 rounded-lg px-4 py-3 text-red-300 text-sm whitespace-pre-line leading-relaxed">
              {run.error}
            </div>
          )}
        </div>

        {/* Branch distribution */}
        {run.status === "done" && Object.keys(run.branch_distribution).length > 0 && (
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-6">
            <h2 className="font-semibold mb-4">Condition distribution</h2>
            <div className="flex flex-col gap-2">
              {Object.entries(run.branch_distribution).map(([branch, count]) => (
                <div key={branch} className="flex items-center gap-3">
                  <div className="flex-1 text-sm text-gray-300 truncate">{branch}</div>
                  <div className="text-sm font-mono text-white">{count}</div>
                  <div className="w-24 h-2 bg-gray-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-blue-500 rounded-full"
                      style={{ width: `${(count / run.n_participants) * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Results preview */}
        {run.status === "done" && <RunResults runId={run.id} />}

        {/* Actions */}
        {run.status === "done" && (
          <div className="flex gap-3">
            <a
              href={api.downloadUrl(run.id)}
              className="flex-1 text-center bg-blue-600 hover:bg-blue-500 text-white font-semibold py-3 rounded-lg transition"
            >
              Download CSV
            </a>
            <button
              onClick={() => router.push("/run/new")}
              className="flex-1 border border-gray-700 hover:border-gray-500 text-gray-300 py-3 rounded-lg transition"
            >
              New run
            </button>
          </div>
        )}
        {run.status === "failed" && (
          <button
            onClick={() => router.push("/run/new")}
            className="w-full border border-gray-700 hover:border-gray-500 text-gray-300 py-3 rounded-lg transition"
          >
            Try again
          </button>
        )}

        {isActive && (
          <button
            onClick={handleCancel}
            disabled={cancelling}
            className="w-full border border-red-800 hover:border-red-600 disabled:opacity-40 text-red-400 hover:text-red-300 py-3 rounded-lg transition text-sm"
          >
            {cancelling ? "Cancelling…" : "Cancel this run"}
          </button>
        )}

        {/* Always available — researchers often realize here they want more runs */}
        <a
          href="/dashboard#buy-credits"
          className="mt-3 block text-center text-sm text-blue-400 hover:text-blue-300"
        >
          Need more participants? Buy more credits →
        </a>
      </div>
    </main>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-gray-500 text-xs mb-0.5">{label}</div>
      <div className="font-medium text-white">{value}</div>
    </div>
  );
}

function formatDuration(start: string, end: string): string {
  const secs = Math.round((new Date(end).getTime() - new Date(start).getTime()) / 1000);
  if (secs < 60) return `${secs}s`;
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  if (m < 60) return s > 0 ? `${m}m ${s}s` : `${m}m`;
  const h = Math.floor(m / 60);
  const rem = m % 60;
  return rem > 0 ? `${h}h ${rem}m` : `${h}h`;
}
