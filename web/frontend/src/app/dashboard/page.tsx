"use client";
import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api, type Run } from "@/lib/api";

export default function Dashboard() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-gray-950 flex items-center justify-center text-white">Loading…</div>
    }>
      <DashboardInner />
    </Suspense>
  );
}

function DashboardInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [user, setUser] = useState<{ email: string; credits: number } | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [packs, setPacks] = useState<{ id: string; credits: number; price_cents: number; label: string }[]>([]);
  const [checkingOut, setCheckingOut] = useState<string | null>(null);
  const purchased = searchParams.get("purchase") === "success";

  useEffect(() => {
    api.me().then(setUser).catch(() => router.push("/"));
    api.listRuns().then(setRuns).catch(() => {});
    api.packs().then(setPacks).catch(() => {});
  }, [router]);

  // Poll runs that are in-progress
  useEffect(() => {
    const active = runs.filter((r) => !["done", "failed"].includes(r.status));
    if (active.length === 0) return;
    const t = setTimeout(async () => {
      const updated = await api.listRuns().catch(() => runs);
      setRuns(updated);
    }, 5000);
    return () => clearTimeout(t);
  }, [runs]);

  async function handleCheckout(packId: string) {
    setCheckingOut(packId);
    try {
      const { checkout_url } = await api.checkout(packId);
      window.location.assign(checkout_url);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Checkout failed.";
      // A 401 here means the session expired between page load and click.
      // Send them to the login form to sign in again via email link rather
      // than showing a confusing raw error.
      if (/log ?in|session|401|not logged/i.test(msg)) {
        alert("Your session has expired. Please log in again — enter your email to get a sign-in link.");
        router.push("/#login");
        return;
      }
      alert(msg);
      setCheckingOut(null);
    }
  }

  async function handleLogout() {
    await api.logout();
    router.push("/");
  }

  if (!user) return <div className="min-h-screen bg-gray-950 flex items-center justify-center text-white">Loading…</div>;

  return (
    <main className="min-h-screen bg-gray-950 text-white">
      <nav className="border-b border-gray-800 px-6 py-4 flex items-center justify-between max-w-6xl mx-auto">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/logo-wordmark.png" alt="Doppelganger Labs" className="h-8 w-auto" />
        <div className="flex items-center gap-4">
          <span className="text-gray-400 text-sm">{user.email}</span>
          <button onClick={handleLogout} className="text-sm text-gray-500 hover:text-gray-300">Log out</button>
        </div>
      </nav>

      <div className="max-w-5xl mx-auto px-6 py-10">
        {purchased && (
          <div className="bg-green-900/40 border border-green-700 rounded-xl px-5 py-4 mb-6 text-green-300">
            ✓ Credits added to your account!
          </div>
        )}

        {/* Credits + new run */}
        <div className="flex flex-col sm:flex-row gap-4 mb-10">
          <div className="flex-1 bg-gray-900 border border-gray-800 rounded-xl p-6">
            <div className="text-gray-400 text-sm mb-1">Credit balance</div>
            <div className="text-4xl font-bold">{user.credits}</div>
            <div className="text-gray-500 text-sm mt-1">participants remaining</div>
          </div>
          <div className="flex-1 bg-gray-900 border border-gray-800 rounded-xl p-6 flex flex-col justify-between">
            <div className="text-gray-400 text-sm mb-3">Ready to run a study?</div>
            <button
              onClick={() => router.push("/run/new")}
              className="bg-blue-600 hover:bg-blue-500 text-white font-semibold px-6 py-3 rounded-lg transition w-full"
            >
              + New simulation
            </button>
          </div>
        </div>

        {/* Buy credits */}
        <section id="buy-credits" className="mb-10 scroll-mt-20">
          <h2 className="font-semibold text-gray-300 mb-4">Buy credits</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {packs.map((pack) => (
              <button
                key={pack.id}
                onClick={() => handleCheckout(pack.id)}
                disabled={checkingOut === pack.id}
                className="bg-gray-900 border border-gray-800 hover:border-gray-600 rounded-xl p-4 text-left transition disabled:opacity-50"
              >
                <div className="font-bold text-lg">${(pack.price_cents / 100).toFixed(2)}</div>
                <div className="text-gray-400 text-sm">{pack.credits} credits</div>
                <div className="text-gray-500 text-xs mt-1">{pack.label}</div>
              </button>
            ))}
          </div>
        </section>

        {/* Run history */}
        <section>
          <h2 className="font-semibold text-gray-300 mb-4">Your runs</h2>
          {runs.length === 0 ? (
            <p className="text-gray-600 text-sm">No runs yet. Start your first simulation above.</p>
          ) : (
            <div className="flex flex-col gap-3">
              {runs.map((run) => (
                <RunRow key={run.id} run={run} />
              ))}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

function RunRow({ run }: { run: Run }) {
  const router = useRouter();
  const statusColors: Record<string, string> = {
    converting: "text-yellow-400",
    running: "text-blue-400",
    done: "text-green-400",
    failed: "text-red-400",
  };
  const color = statusColors[run.status] ?? "text-gray-400";
  const isActive = !["done", "failed"].includes(run.status);

  return (
    <div
      className="bg-gray-900 border border-gray-800 rounded-xl px-5 py-4 flex items-center justify-between cursor-pointer hover:border-gray-700 transition"
      onClick={() => router.push(`/run/${run.id}`)}
    >
      <div>
        <div className="font-medium text-sm">{run.original_survey_id}</div>
        <div className="text-gray-500 text-xs mt-0.5">
          {run.n_participants} participants · {run.is_smoke_test ? "trial run" : "full run"} ·{" "}
          {new Date(run.created_at).toLocaleDateString()}
        </div>
      </div>
      <div className="flex items-center gap-3">
        {isActive && (
          <span className="inline-block w-2 h-2 bg-blue-400 rounded-full animate-pulse" />
        )}
        <span className={`text-sm font-medium capitalize ${color}`}>{run.status}</span>
        <span className="text-gray-600">→</span>
      </div>
    </div>
  );
}
