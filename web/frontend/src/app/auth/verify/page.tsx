"use client";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function VerifyInner() {
  const searchParams = useSearchParams();
  const [error, setError] = useState("");

  useEffect(() => {
    const token = searchParams.get("token");
    if (!token) { setError("missing"); return; }

    // Use fetch with redirect:manual so we can intercept errors (e.g. expired
    // token → 400) instead of the browser showing raw backend JSON.
    fetch(`${BASE}/auth/verify?token=${token}`, {
      credentials: "include",
      redirect: "manual",
    }).then((res) => {
      if (res.type === "opaqueredirect" || res.ok) {
        // Backend set the cookie and issued a redirect — follow it.
        window.location.href = "/dashboard";
      } else {
        return res.json().then((body) => {
          setError(body?.detail || "expired");
        }).catch(() => setError("expired"));
      }
    }).catch(() => setError("expired"));
  }, [searchParams]);

  if (error) {
    return (
      <main className="min-h-screen bg-gray-950 flex items-center justify-center text-white px-6">
        <div className="max-w-sm w-full text-center">
          <div className="text-4xl mb-4">🔗</div>
          <h1 className="text-xl font-semibold mb-2">
            {error === "missing" ? "Invalid link" : "This link has expired"}
          </h1>
          <p className="text-gray-400 text-sm leading-relaxed mb-6">
            {error === "missing"
              ? "This sign-in link is missing or malformed."
              : "Magic links expire after 15 minutes for security. Request a fresh one and try again."}
          </p>
          <a
            href="/#login"
            className="inline-block bg-blue-600 hover:bg-blue-500 text-white font-semibold px-6 py-3 rounded-lg transition"
          >
            Get a new sign-in link
          </a>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-gray-950 flex items-center justify-center text-white">
      <p className="text-gray-400">Verifying your magic link…</p>
    </main>
  );
}

export default function Verify() {
  return (
    <Suspense fallback={
      <main className="min-h-screen bg-gray-950 flex items-center justify-center text-white">
        <p className="text-gray-400">Loading…</p>
      </main>
    }>
      <VerifyInner />
    </Suspense>
  );
}
