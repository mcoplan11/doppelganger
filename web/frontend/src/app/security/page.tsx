import type { Metadata } from "next";
import { BlogShell } from "@/components/blog-shell";

export const metadata: Metadata = {
  title: "Security — what Doppelganger does with your Qualtrics API token",
  description:
    "Exactly which Qualtrics API endpoints Doppelganger calls, what is read vs. written, how your token is stored, and how to keep your exposure to a minimum.",
  alternates: { canonical: "/security" },
  openGraph: {
    type: "article",
    url: "/security",
    title: "Security — what Doppelganger does with your Qualtrics API token",
    description:
      "Every Qualtrics API call we make, what is read vs. written, how your token is stored, and how to minimize your exposure.",
  },
};

const ENDPOINTS: Array<{ call: string; kind: "Read" | "Write"; what: string }> = [
  {
    call: "GET /whoami",
    kind: "Read",
    what: "Validates your token and reads your user ID so the AI copy is created under your account.",
  },
  {
    call: "GET /survey-definitions/{your survey}",
    kind: "Read",
    what: "Reads the structure (questions, blocks, flow) of the one survey you point us at. We never read its collected responses.",
  },
  {
    call: "POST /surveys (copy)",
    kind: "Write",
    what: "Creates a new survey in your account — a copy named “[Your survey] - AI Copy”. Your original is not modified.",
  },
  {
    call: "PUT/POST/DELETE /survey-definitions/{AI copy}/…",
    kind: "Write",
    what: "Adjusts the AI copy for Sessions API compatibility (e.g. sliders become numeric entry). These writes target the copy only.",
  },
  {
    call: "PUT /surveys/{AI copy}",
    kind: "Write",
    what: "Activates the AI copy so sessions can run against it.",
  },
  {
    call: "POST /surveys/{AI copy}/sessions",
    kind: "Write",
    what: "Starts and advances AI respondent sessions on the copy. Responses are recorded in the copy's own Data & Analysis tab.",
  },
  {
    call: "DELETE /surveys/{AI copy}",
    kind: "Write",
    what: "Deletes an AI copy that failed or produced no responses, so empty copies don't clutter your account.",
  },
];

function H2({ children }: { children: React.ReactNode }) {
  return <h2 className="font-serif text-2xl font-bold text-slate-900 mt-10 mb-3">{children}</h2>;
}
function P({ children }: { children: React.ReactNode }) {
  return <p className="text-slate-700 leading-relaxed mb-4">{children}</p>;
}

export default function Security() {
  return (
    <BlogShell>
      <article className="max-w-2xl mx-auto px-6 pt-16 pb-8">
        <p className="text-xs font-semibold uppercase tracking-wider text-blue-700 mb-3">Trust &amp; security</p>
        <h1 className="font-serif text-3xl sm:text-4xl font-bold text-slate-900 mb-3 leading-tight">
          What we do with your Qualtrics API token
        </h1>
        <p className="text-slate-600 mb-8">
          A Qualtrics API token is a powerful credential, and you should know exactly what any tool
          does with it before you paste it anywhere. This page lists every API call Doppelganger
          makes, what we store, and how to keep your exposure to a minimum. Written for you to
          forward to your IT department or Qualtrics brand administrator.
        </p>

        <div className="bg-slate-50 border border-slate-200 rounded-xl p-6 mb-8">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">The short version</p>
          <ul className="text-slate-700 leading-relaxed text-[15px] list-disc pl-5 space-y-1">
            <li>We read the structure of the one survey you specify. We never read its collected responses.</li>
            <li>We never modify your original survey. All writes go to a separate AI copy we create in your account.</li>
            <li>We never touch contact lists, mailing lists, other surveys&apos; data, or user administration.</li>
            <li>Your token is encrypted at rest and never shared with third parties, including the AI model providers.</li>
            <li>You can invalidate the token at any moment by regenerating it in Qualtrics — including right after your run.</li>
          </ul>
        </div>

        <H2>If you&apos;d rather not share a token at all</H2>
        <P>
          You can skip the API entirely: upload your survey&apos;s .qsf export (Tools &rarr;
          Import/Export &rarr; Export Survey) and Doppelganger runs it through our own survey
          engine — randomizer, branching, and display logic included. Nothing touches any
          Qualtrics account, no credential changes hands, and results arrive in your dashboard
          and as a CSV download. The rest of this page covers the API connection mode, which you
          only need if you want AI responses recorded in your own Qualtrics Data &amp; Analysis
          tab.
        </P>

        <H2>Why the API connection exists</H2>
        <P>
          In API mode, Doppelganger runs AI respondents through the official Qualtrics Sessions
          API, which plays your survey back server-side — your own randomizer assigns conditions
          and your own branching and skip logic fire, exactly as they would for a human
          participant — and responses land in a copy inside your own account, where you analyze
          them like any dataset.
        </P>

        <H2>Every endpoint we call</H2>
        <div className="overflow-hidden rounded-lg border border-slate-200 mb-6">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 text-slate-600">
                <th className="text-left font-semibold px-4 py-2">API call</th>
                <th className="text-left font-semibold px-4 py-2 w-20">Type</th>
                <th className="text-left font-semibold px-4 py-2">What it does</th>
              </tr>
            </thead>
            <tbody>
              {ENDPOINTS.map((e) => (
                <tr key={e.call} className="border-t border-slate-100 align-top">
                  <td className="px-4 py-2 font-mono text-xs text-slate-700 whitespace-nowrap">{e.call}</td>
                  <td className={`px-4 py-2 font-semibold ${e.kind === "Read" ? "text-green-700" : "text-amber-600"}`}>
                    {e.kind}
                  </td>
                  <td className="px-4 py-2 text-slate-700">{e.what}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <P>
          That is the complete list. We do not call the response-export endpoints, the directory or
          contacts endpoints, the distributions (email) endpoints, or any user-administration
          endpoint. Your run results come from the sessions we ourselves create, never from data
          your human participants submitted.
        </P>

        <H2>The honest limitation: tokens are account-level</H2>
        <P>
          Qualtrics API tokens inherit all of your account&apos;s permissions — Qualtrics does not
          offer per-survey tokens, and its OAuth scopes restrict operations, not which surveys a
          credential can see. We cannot change that, so instead of asking you to trust us
          indefinitely, we recommend you shrink the window during which trust is required:
        </P>
        <ul className="list-disc pl-6 space-y-2 text-slate-700 leading-relaxed mb-4">
          <li>
            <strong>Regenerate your token after your run.</strong> Generating a new token in
            Qualtrics (Account Settings &rarr; Qualtrics IDs &rarr; API) instantly invalidates the
            old one. Your credential can be dead an hour after you created it, and nothing we hold
            can access your account afterward.
          </li>
          <li>
            <strong>Use a sandbox account.</strong> If your main account holds sensitive data, ask
            your brand administrator for API access on a secondary account, import your study&apos;s
            QSF there, and run Doppelganger against that. A token for an account containing one
            survey is effectively a per-survey token.
          </li>
        </ul>

        <H2>How we handle your token and data</H2>
        <P>
          Your token is encrypted at rest (Fernet symmetric encryption) and decrypted only in
          memory while your run executes. It is never written to logs and never sent to any third
          party. In particular, the AI model providers that generate responses receive your survey
          text and images — they never receive your token, your account details, or your
          participants&apos; data. If you want your stored token removed after a run, email{" "}
          <a href="mailto:hello@doppelgangerlabs.com" className="text-blue-700 hover:text-blue-800 underline underline-offset-2">
            hello@doppelgangerlabs.com
          </a>{" "}
          and we will delete it — or simply regenerate it in Qualtrics, which renders the stored
          copy useless either way.
        </P>
        <P>
          AI respondent answers live in two places: the AI copy in your own Qualtrics account
          (where you analyze them like any other dataset), and our database (so your dashboard can
          display results and exports). They are your data; we do not sell them or use them to
          train models.
        </P>

        <H2>Questions</H2>
        <P>
          If your IT department or brand administrator has questions this page doesn&apos;t answer,
          have them email{" "}
          <a href="mailto:hello@doppelgangerlabs.com" className="text-blue-700 hover:text-blue-800 underline underline-offset-2">
            hello@doppelgangerlabs.com
          </a>{" "}
          — we are happy to walk through the integration with them directly.
        </P>

        <p className="text-xs text-slate-400 italic mt-8 border-t border-slate-200 pt-6">
          This page describes Doppelganger&apos;s behavior as of November 2026 and is kept in sync
          with the product. Doppelganger is not affiliated with Qualtrics.
        </p>
      </article>
    </BlogShell>
  );
}
