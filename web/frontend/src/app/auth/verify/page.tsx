"use client";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function VerifyInner() {
  const searchParams = useSearchParams();
  const [error, setError] = useState("");

  useEffect(() => {
    const token = searchParams.get("token");
    if (!token) { setError("No token found."); return; }
    // Redirect to backend — it sets the cookie and 302s to /dashboard
    window.location.href = `${BASE}/auth/verify?token=${token}`;
  }, [searchParams]);

  return (
    <main className="min-h-screen bg-gray-950 flex items-center justify-center text-white">
      {error
        ? <p className="text-red-400">{error}</p>
        : <p className="text-gray-400">Verifying your magic link…</p>
      }
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
