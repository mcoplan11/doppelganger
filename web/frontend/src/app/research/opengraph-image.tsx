import { ImageResponse } from "next/og";

// Dedicated Open Graph card for the research report, so shared links unfurl with the
// paper's headline result instead of the generic site card. Same conventions as the
// homepage opengraph-image: inline styles, default font, 1200x630, generated at build.
export const alt =
  "Do large language models reproduce classic human decision biases? An off-the-shelf replication benchmark.";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function ResearchOpengraphImage() {
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
        <div style={{ fontSize: 28, color: "#93c5fd", fontWeight: 600, textTransform: "uppercase", letterSpacing: 2 }}>
          Doppelganger Labs · Research
        </div>
        <div style={{ fontSize: 58, fontWeight: 800, lineHeight: 1.08, marginTop: 24, maxWidth: 1000 }}>
          Do LLMs reproduce classic human decision biases?
        </div>
        <div style={{ fontSize: 30, color: "#cbd5e1", marginTop: 28, maxWidth: 1000 }}>
          An ensemble of models reproduced 15.5 of 17 effects (91%) on Twin-2K-500.
        </div>
        <div style={{ fontSize: 24, color: "#64748b", marginTop: "auto" }}>doppelgangerlabs.com/research</div>
      </div>
    ),
    { ...size },
  );
}
