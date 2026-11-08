"use client";
import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { PayPalButtons, PayPalScriptProvider } from "@paypal/react-paypal-js";
import { api, type Run } from "@/lib/api";

const PAYPAL_CLIENT_ID = process.env.NEXT_PUBLIC_PAYPAL_CLIENT_ID ?? "";

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
  const [user, setUser] = useState<{ email: string; credits: number; heard_from?: string | null } | null>(null);
  const [heardFrom, setHeardFrom] = useState("");
  const [heardFromDone, setHeardFromDone] = useState(false);
  const [runs, setRuns] = useState<Run[]>([]);
  const [packs, setPacks] = useState<{ id: string; credits: number; price_cents: number; label: string }[]>([]);
  const [checkingOut, setCheckingOut] = useState<string | null>(null);
  const [selectedPack, setSelectedPack] = useState<string | null>(null);
  const [paypalCredits, setPaypalCredits] = useState<number | null>(null);
  const purchased = searchParams.get("purchase") === "success" || paypalCredits != null;

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

        {/* One-time attribution prompt — hidden once answered or dismissed */}
        {!user.heard_from && !heardFromDone && (
          <div className="bg-gray-900 border border-gray-800 rounded-xl px-5 py-4 mb-6 flex flex-col sm:flex-row sm:items-center gap-3">
            <span className="text-gray-300 text-sm flex-1">How did you hear about Doppelganger?</span>
            <select
              value={heardFrom}
              onChange={(e) => setHeardFrom(e.target.value)}
              className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white"
            >
              <option value="">Select…</option>
              <option value="google_search">Google search</option>
              <option value="chatgpt_ai">ChatGPT or another AI tool</option>
              <option value="colleague">A colleague or friend</option>
              <option value="social_media">Social media</option>
              <option value="conference_listserv">Conference or mailing list</option>
              <option value="other">Other</option>
            </select>
            <div className="flex gap-2">
              <button
                disabled={!heardFrom}
                onClick={() => {
                  api.setHeardFrom(heardFrom).catch(() => {});
                  setHeardFromDone(true);
                }}
                className="bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white text-sm font-medium px-4 py-2 rounded-lg"
              >
                Save
              </button>
              <button
                onClick={() => {
                  api.setHeardFrom("dismissed").catch(() => {});
                  setHeardFromDone(true);
                }}
                className="text-gray-500 hover:text-gray-300 text-sm px-2"
              >
                ✕
              </button>
            </div>
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

        {/* Buy credits — PayPal is the primary checkout; card (Stripe) fallback.
            Without a PayPal client ID, pack clicks go straight to card checkout. */}
        <section id="buy-credits" className="mb-10 scroll-mt-20">
          <h2 className="font-semibold text-gray-300 mb-4">Buy credits</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {packs.map((pack) => {
              const isSelected = selectedPack === pack.id;
              return (
                <button
                  key={pack.id}
                  onClick={() =>
                    PAYPAL_CLIENT_ID
                      ? setSelectedPack(isSelected ? null : pack.id)
                      : handleCheckout(pack.id)
                  }
                  disabled={checkingOut === pack.id}
                  className={`bg-gray-900 border rounded-xl p-4 text-left transition disabled:opacity-50 ${
                    isSelected
                      ? "border-blue-500 ring-1 ring-blue-500/50"
                      : "border-gray-800 hover:border-gray-600"
                  }`}
                >
                  <div className="font-bold text-lg">${(pack.price_cents / 100).toFixed(2)}</div>
                  <div className="text-gray-400 text-sm">{pack.credits} credits</div>
                  <div className="text-gray-500 text-xs mt-1">{pack.label}</div>
                </button>
              );
            })}
          </div>

          {PAYPAL_CLIENT_ID && selectedPack && (() => {
            const pack = packs.find((p) => p.id === selectedPack);
            if (!pack) return null;
            return (
              <div className="mt-4 bg-gray-900 border border-gray-800 rounded-xl p-5 max-w-md">
                <div className="text-sm text-gray-300 mb-4">
                  <span className="font-semibold">{pack.label}</span> — {pack.credits} credits for{" "}
                  <span className="font-semibold">${(pack.price_cents / 100).toFixed(2)}</span>
                </div>
                <PayPalScriptProvider options={{ clientId: PAYPAL_CLIENT_ID, currency: "USD" }}>
                  <PayPalButtons
                    forceReRender={[selectedPack]}
                    style={{ layout: "vertical", label: "paypal" }}
                    createOrder={async () => {
                      const { order_id } = await api.paypalCreateOrder(pack.id);
                      return order_id;
                    }}
                    onApprove={async (data) => {
                      try {
                        const res = await api.paypalCaptureOrder(data.orderID);
                        setPaypalCredits(res.credits_added);
                        setUser((u) => (u ? { ...u, credits: res.balance } : u));
                        setSelectedPack(null);
                        window.scrollTo({ top: 0, behavior: "smooth" });
                      } catch (err: unknown) {
                        alert(err instanceof Error ? err.message : "Payment capture failed.");
                      }
                    }}
                    onError={() => {
                      alert("PayPal checkout failed. Please try again or pay by card.");
                    }}
                  />
                </PayPalScriptProvider>
                <button
                  onClick={() => handleCheckout(pack.id)}
                  disabled={checkingOut === pack.id}
                  className="w-full mt-1 text-xs text-gray-500 hover:text-gray-300 transition disabled:opacity-50"
                >
                  or pay by card instead
                </button>
              </div>
            );
          })()}
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
        <div className="font-medium text-sm flex items-center gap-2">
          {run.original_survey_id}
          {run.is_sample && (
            <span className="text-[10px] font-semibold uppercase tracking-wider text-purple-300 border border-purple-700/60 bg-purple-950/40 rounded px-1.5 py-0.5">
              Sample
            </span>
          )}
        </div>
        <div className="text-gray-500 text-xs mt-0.5">
          {run.n_participants} participants ·{" "}
          {run.is_sample ? "sample study" : run.is_smoke_test ? "trial run" : "full run"} ·{" "}
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
