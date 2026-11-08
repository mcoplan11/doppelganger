"use client";

import { useEffect } from "react";

// First-touch attribution: on the visitor's first page load (any route), stash
// the referrer, landing path, and UTM params in localStorage. Sent along with
// the magic-link request at signup (see api.requestMagicLink) and stored once
// on the user row — never overwritten by later visits.
export function AttributionCapture() {
  useEffect(() => {
    try {
      if (localStorage.getItem("dg_attribution")) return;
      const params = new URLSearchParams(window.location.search);
      const utm: Record<string, string> = {};
      for (const k of ["utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"]) {
        const v = params.get(k);
        if (v) utm[k] = v.slice(0, 200);
      }
      localStorage.setItem(
        "dg_attribution",
        JSON.stringify({
          referrer: document.referrer.slice(0, 500),
          landing: window.location.pathname.slice(0, 200),
          ...utm,
          ts: new Date().toISOString(),
        })
      );
    } catch {
      // localStorage unavailable (private mode etc.) — attribution is best-effort
    }
  }, []);
  return null;
}
