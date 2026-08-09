import { ImageResponse } from "next/og";

// Site-level Open Graph image for the homepage — generated at build time so shared
// links (X, Slack, iMessage, email) unfurl with a branded card. Uses only inline
// styles and the default font to stay dependency-free.
export const alt = "Doppelganger — Pretest your survey with AI respondents";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          height: "100%",
          width: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: "80px",
          background: "#0f172a",
          color: "white",
        }}
      >
        <div style={{ fontSize: 34, color: "#93c5fd", fontWeight: 600 }}>Doppelganger</div>
        <div style={{ fontSize: 74, fontWeight: 800, lineHeight: 1.05, marginTop: 24, maxWidth: 940 }}>
          Pretest your survey with AI respondents
        </div>
        <div style={{ fontSize: 32, color: "#cbd5e1", marginTop: 28, maxWidth: 940 }}>
          Catch problems and gauge your effect before you pay for participants.
        </div>
        <div style={{ fontSize: 26, color: "#64748b", marginTop: "auto" }}>doppelgangerlabs.com</div>
      </div>
    ),
    { ...size },
  );
}
