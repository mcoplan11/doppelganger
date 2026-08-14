"use client";
import { useEffect, useRef, useState } from "react";
import {
  api,
  isEnsembleResults,
  type DistItem,
  type EnsembleResults,
  type Interpretation,
  type ModelResult,
  type QuestionResult,
  type ResultsSummary,
  type Summary,
} from "@/lib/api";

export default function RunResults({ runId }: { runId: number }) {
  const [results, setResults] = useState<ResultsSummary | EnsembleResults | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getResults(runId)
      .then(setResults)
      .catch(() => setResults(null))
      .finally(() => setLoading(false));
  }, [runId]);

  if (loading) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-6 text-gray-500 text-sm">
        Loading results…
      </div>
    );
  }
  if (isEnsembleResults(results)) return <EnsembleView ensemble={results} />;
  if (!results?.available || results.questions.length === 0) return null;
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-6">
      <h2 className="font-semibold mb-1">Results preview</h2>
      <p className="text-gray-500 text-xs mb-6 leading-relaxed">
        Based on {results.n_completed} AI {results.n_completed === 1 ? "respondent" : "respondents"}
        {results.has_conditions ? ", broken out by condition" : ""}. Directional only — a gut-check
        on whether your design produces a signal, not a substitute for human data.
      </p>
      <ModelResultsBody results={results} />
    </div>
  );
}

// ── Ensemble: one independent panel per (anonymized) model ────────────────────
function EnsembleView({ ensemble }: { ensemble: EnsembleResults }) {
  const models = ensemble.models ?? [];
  const withData = models.filter((m) => m.results?.available && m.results.questions.length > 0);
  const [active, setActive] = useState(0);

  if (withData.length === 0) return null;
  const activeModel: ModelResult = withData[Math.min(active, withData.length - 1)];

  return (
    <>
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-6">
      <h2 className="font-semibold mb-1">Results preview — model ensemble</h2>
      <p className="text-gray-500 text-xs mb-4 leading-relaxed">
        Your survey was run through {models.length} AI models — shown anonymously as Model A, B, and
        C — each answering as a panel of {activeModel.results.n_completed ?? activeModel.n_completed}{" "}
        simulated participants.
      </p>

      {/* Why do I see Model A, B, and C? */}
      <div className="mb-3 rounded-lg border border-blue-900/60 bg-blue-950/30 px-4 py-3 text-xs text-blue-200 leading-relaxed">
        <span className="font-semibold">Why do I see Model A, B, and C?</span> The simulated
        participants are the <span className="font-semibold">same</span> across all three — the same
        personas answering in character. What changes is the underlying AI model (the LLM) we send
        them to: Model A, B, and C are three different LLMs. No single LLM is best at everything —
        one may pick up an effect that another misses — so we test your survey across all three and
        show each model&rsquo;s results separately. The real model names are kept anonymous.
      </div>

      {/* How to read this */}
      <div className="mb-5 rounded-lg border border-blue-900/60 bg-blue-950/30 px-4 py-3 text-xs text-blue-200 leading-relaxed">
        <span className="font-semibold">How to read this:</span> if your manipulation produces a
        real effect, it should move answers in the expected direction in{" "}
        <span className="font-semibold">at least one</span> model — that&rsquo;s a positive signal
        worth fielding. When several models agree, the signal is stronger. A flat result across
        every model is a hint your design may not produce the effect (directional only — not a
        substitute for human data).
      </div>

      {/* Model tabs */}
      <div className="flex flex-wrap gap-2 mb-5">
        {withData.map((m, i) => {
          const idx = i;
          const isActive = withData[Math.min(active, withData.length - 1)].slug === m.slug;
          return (
            <button
              key={m.slug}
              onClick={() => setActive(idx)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors border ${
                isActive
                  ? "bg-blue-600 border-blue-500 text-white"
                  : "bg-gray-800 border-gray-700 text-gray-300 hover:bg-gray-700"
              }`}
            >
              {m.label}
              <span className={`ml-1.5 ${isActive ? "text-blue-200" : "text-gray-500"}`}>
                n={m.results.n_completed ?? m.n_completed}
              </span>
            </button>
          );
        })}
      </div>

      {models.some((m) => m.n_completed === 0) && (
        <p className="text-amber-400/80 text-xs mb-4">
          {models.filter((m) => m.n_completed === 0).map((m) => m.label).join(", ")} produced no
          usable responses and {models.filter((m) => m.n_completed === 0).length === 1 ? "is" : "are"} not shown.
        </p>
      )}

      <ModelResultsBody key={activeModel.slug} results={activeModel.results} />
    </div>
    <InterpretationCard interp={ensemble.interpretation} />
    </>
  );
}

// AI results-interpreter — a model-generated read of the run (backend
// interpreter.py). Rendered below the per-model distributions as a closing
// "what this means / what to fix" summary after the researcher has seen the numbers.
function InterpretationCard({ interp }: { interp?: Interpretation }) {
  if (!interp) return null;
  return (
    <div className="bg-gradient-to-br from-blue-950/40 to-gray-900 border border-blue-900/60 rounded-xl p-6 mb-6">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xs font-semibold uppercase tracking-wider text-blue-300">
          AI analysis
        </span>
        <span className="text-[10px] text-gray-500 border border-gray-700 rounded px-1.5 py-0.5">
          auto-generated
        </span>
      </div>
      <p className="text-white font-medium leading-snug mb-4">{interp.headline}</p>

      {interp.observations?.length > 0 && (
        <div className="mb-4">
          <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">
            Key observations
          </div>
          <ul className="list-disc list-inside space-y-1.5 text-sm text-gray-300 leading-relaxed marker:text-blue-500">
            {interp.observations.map((o, i) => (
              <li key={i}>{o}</li>
            ))}
          </ul>
        </div>
      )}

      {interp.issues_to_check?.length > 0 && (
        <div className="mb-4">
          <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">
            Fix before fielding
          </div>
          <div className="flex flex-col gap-2">
            {interp.issues_to_check.map((issue, i) => (
              <div key={i} className="rounded-lg border border-amber-900/50 bg-amber-950/20 px-3 py-2.5">
                <div className="text-sm text-amber-200 font-medium leading-snug">{issue.question}</div>
                <div className="text-xs text-gray-300 mt-1 leading-relaxed">{issue.concern}</div>
                <div className="text-xs text-blue-300 mt-1 leading-relaxed">
                  <span className="text-gray-500">Suggestion: </span>{issue.suggestion}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {interp.recommendation && (
        <div className="rounded-lg bg-gray-800/60 border border-gray-700 px-3 py-2.5">
          <span className="text-xs text-gray-500 uppercase tracking-wider">Recommendation </span>
          <span className="text-sm text-gray-200">{interp.recommendation}</span>
        </div>
      )}

      <p className="text-[11px] text-gray-600 mt-4 leading-relaxed">
        Generated by an AI model from the anonymized response distributions above. A screening
        aid, not a substitute for human data.
      </p>
    </div>
  );
}

// Shared question rendering for a single model's ResultsSummary.
function ModelResultsBody({ results }: { results: ResultsSummary }) {
  if (!results.available || results.questions.length === 0) {
    return <p className="text-gray-500 text-sm">No results available for this model.</p>;
  }
  return (
    <>
      <QuestionTOC questions={results.questions} />
      <div className="flex flex-col divide-y divide-gray-800">
        {results.questions.map((q) => (
          <QuestionBlock key={q.qid} q={q} hasConditions={!!results.has_conditions} />
        ))}
      </div>
    </>
  );
}

function QuestionTOC({ questions }: { questions: QuestionResult[] }) {
  const scrollTo = (qid: string) => {
    document.getElementById(`q-${qid}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };
  return (
    <div className="mb-6 border border-gray-800 rounded-lg overflow-hidden">
      <div className="px-3 py-2 bg-gray-800/50 text-xs text-gray-500 uppercase tracking-wider">
        All questions — click to jump
      </div>
      <div className="flex flex-col divide-y divide-gray-800">
        {questions.map((q, i) => (
          <button
            key={q.qid}
            onClick={() => scrollTo(q.qid)}
            title={q.prompt}
            className="flex items-center gap-3 px-3 py-2 text-left hover:bg-gray-800 transition-colors"
          >
            <span className="shrink-0 w-6 text-gray-600 text-xs font-mono text-right">{i + 1}</span>
            <span className="text-gray-300 text-xs truncate">{q.prompt}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function QuestionBlock({ q, hasConditions }: { q: QuestionResult; hasConditions: boolean }) {
  return (
    <div id={`q-${q.qid}`} className="py-5 first:pt-0 last:pb-0 scroll-mt-4">
      <div className="text-sm font-medium text-white mb-3 leading-snug" title={q.prompt}>{q.prompt}</div>

      {q.overall.kind === "text" && <TextResponses responses={q.overall.responses ?? []} />}

      {q.overall.kind === "matrix" && (
        <MatrixView q={q} hasConditions={hasConditions} />
      )}

      {(q.overall.kind === "choice" || q.overall.kind === "multi") && (
        hasConditions && q.by_condition
          ? <ChoiceByCondition q={q} />
          : <SingleSummary summary={q.overall} />
      )}
    </div>
  );
}

// ── Choice / scale, no conditions ────────────────────────────────────────────
function SingleSummary({ summary }: { summary: Summary }) {
  if (summary.mean != null) {
    return (
      <>
        <div className="text-xs text-gray-500 mb-2 uppercase tracking-wider">Mean response</div>
        <MeanBar mean={summary.mean} bounds={scaleBounds(summary.distribution)} n={summary.n} />
      </>
    );
  }
  return (
    <>
      <div className="text-xs text-gray-500 mb-2 uppercase tracking-wider">Response count</div>
      <DistributionBars dist={summary.distribution ?? []} />
    </>
  );
}

// ── Choice / scale, broken out by condition (the headline view) ──────────────
function ChoiceByCondition({ q }: { q: QuestionResult }) {
  const isScale = q.overall.mean != null;
  const bounds = scaleBounds(q.overall.distribution);

  if (isScale) {
    return (
      <>
        <div className="text-xs text-gray-500 mb-2 uppercase tracking-wider">Mean response by condition</div>
        <div className="flex flex-col gap-2.5">
          {q.by_condition!.map((c) => (
            <MeanBar key={c.condition} label={c.condition} mean={c.mean ?? 0} bounds={bounds} n={c.n} />
          ))}
        </div>
      </>
    );
  }

  // Categorical: a small distribution per condition
  return (
    <>
      <div className="text-xs text-gray-500 mb-2 uppercase tracking-wider">Response count by condition</div>
      <div className="flex flex-col gap-4">
        {q.by_condition!.map((c) => (
          <div key={c.condition}>
            <div className="flex items-center gap-1.5 text-xs text-gray-400 mb-1.5">
              <ConditionLabel name={c.condition} className="max-w-[220px]" />
              <span className="text-gray-600 shrink-0">· n={c.n}</span>
            </div>
            <DistributionBars dist={c.distribution ?? []} />
          </div>
        ))}
      </div>
    </>
  );
}

// ── Matrix ───────────────────────────────────────────────────────────────────
function MatrixView({ q, hasConditions }: { q: QuestionResult; hasConditions: boolean }) {
  const rows = q.overall.rows ?? [];
  if (rows.length === 0) return null;

  if (hasConditions && q.by_condition) {
    const conditions = q.by_condition.map((c) => c.condition);
    const meanFor = (cond: string, rowLabel: string): number | null => {
      const c = q.by_condition!.find((x) => x.condition === cond);
      return c?.rows?.find((r) => r.row === rowLabel)?.mean ?? null;
    };
    return (
      <>
      <div className="text-xs text-gray-500 mb-2 uppercase tracking-wider">Mean response by condition</div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-gray-500">
              <th className="text-left font-normal pb-2 pr-3" />
              {conditions.map((cond) => (
                <th key={cond} className="text-right font-normal pb-2 px-2 max-w-[80px]">
                  <FixedTooltipLabel name={cond} className="max-w-[80px]" />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.row} className="border-t border-gray-800">
                <td className="text-gray-300 py-2 pr-3">{r.row}</td>
                {conditions.map((cond) => {
                  const m = meanFor(cond, r.row);
                  return (
                    <td key={cond} className="text-right py-2 px-2 font-mono text-green-400">
                      {m != null ? m.toFixed(2) : "—"}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      </>
    );
  }

  return (
    <>
      <div className="text-xs text-gray-500 mb-2 uppercase tracking-wider">Mean response per row</div>
      <div className="flex flex-col gap-2.5">
        {rows.map((r) => (
          r.mean != null
            ? <MeanBar key={r.row} label={r.row} mean={r.mean} bounds={scaleBoundsFromRow(r.distribution)} n={r.n} />
            : <div key={r.row}><div className="text-xs text-gray-400 mb-1.5">{r.row}</div><DistributionBars dist={r.distribution} /></div>
        ))}
      </div>
    </>
  );
}

// ── Primitives ────────────────────────────────────────────────────────────────
function ConditionLabel({ name, className = "" }: { name: string; className?: string }) {
  return (
    <span className={`relative group/cl ${className}`}>
      <span className="block truncate">{name}</span>
      <span className="pointer-events-none absolute z-50 left-0 top-full mt-1 bg-gray-900 border border-gray-700 text-white text-xs rounded px-2 py-1.5 whitespace-normal break-words w-max max-w-xs shadow-xl opacity-0 group-hover/cl:opacity-100 transition-opacity duration-150">
        {name}
      </span>
    </span>
  );
}

// For use inside overflow-x-auto containers (e.g. matrix table headers) where
// absolutely positioned children get clipped. Uses fixed positioning keyed to
// the mouse position so the tooltip escapes the overflow context entirely.
function FixedTooltipLabel({ name, className = "" }: { name: string; className?: string }) {
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);
  const ref = useRef<HTMLSpanElement>(null);
  return (
    <span
      ref={ref}
      className={`block truncate cursor-default ${className}`}
      onMouseEnter={(e) => setPos({ x: e.clientX, y: e.clientY })}
      onMouseMove={(e) => setPos({ x: e.clientX, y: e.clientY })}
      onMouseLeave={() => setPos(null)}
    >
      {name}
      {pos && (
        <span
          className="fixed z-50 bg-gray-900 border border-gray-700 text-white text-xs rounded px-2 py-1.5 whitespace-normal break-words max-w-xs shadow-xl pointer-events-none"
          style={{ left: pos.x + 12, top: pos.y + 16 }}
        >
          {name}
        </span>
      )}
    </span>
  );
}

function MeanBar({ label, mean, bounds, n }: { label?: string; mean: number; bounds: Bounds | null; n: number }) {
  const pct = bounds && bounds.max > bounds.min
    ? ((mean - bounds.min) / (bounds.max - bounds.min)) * 100
    : 100;
  return (
    <div className="flex items-center gap-3">
      {label && <div className="w-28 shrink-0 text-xs text-gray-300"><ConditionLabel name={label} /></div>}
      <div className="flex-1 h-2 bg-gray-800 rounded-full overflow-hidden">
        <div className="h-full bg-blue-500 rounded-full transition-all" style={{ width: `${Math.max(2, Math.min(100, pct))}%` }} />
      </div>
      <div className="w-20 shrink-0 text-right text-sm font-mono text-green-400">
        {mean.toFixed(2)} <span className="text-gray-600 text-xs">n={n}</span>
      </div>
    </div>
  );
}

function DistributionBars({ dist }: { dist: DistItem[] }) {
  const max = Math.max(1, ...dist.map((d) => d.count));
  return (
    <div className="flex flex-col gap-1.5">
      {dist.map((d) => (
        <div key={d.label} className="flex items-center gap-3">
          <div className="w-40 shrink-0 text-xs text-gray-300 truncate" title={d.label}>{d.label}</div>
          <div className="flex-1 h-2 bg-gray-800 rounded-full overflow-hidden">
            <div className="h-full bg-blue-500 rounded-full" style={{ width: `${(d.count / max) * 100}%` }} />
          </div>
          <div className="w-8 shrink-0 text-right text-sm font-mono text-gray-300">{d.count}</div>
        </div>
      ))}
    </div>
  );
}

function TextResponses({ responses }: { responses: string[] }) {
  const [expanded, setExpanded] = useState(false);
  const shown = expanded ? responses : responses.slice(0, 3);
  return (
    <div className="flex flex-col gap-2">
      {shown.map((r, i) => (
        <div key={i} className="text-sm text-gray-400 bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 italic">
          “{r}”
        </div>
      ))}
      {responses.length > 3 && (
        <button onClick={() => setExpanded((v) => !v)} className="text-blue-400 hover:text-blue-300 text-xs self-start">
          {expanded ? "Show fewer" : `Show all ${responses.length} responses`}
        </button>
      )}
    </div>
  );
}

// ── helpers ───────────────────────────────────────────────────────────────────
type Bounds = { min: number; max: number };

function scaleBounds(dist?: DistItem[]): Bounds | null {
  if (!dist) return null;
  const recodes = dist.map((d) => d.recode).filter((r): r is number => typeof r === "number");
  if (recodes.length === 0) return null;
  return { min: Math.min(...recodes), max: Math.max(...recodes) };
}

function scaleBoundsFromRow(dist: DistItem[]): Bounds | null {
  return scaleBounds(dist);
}
