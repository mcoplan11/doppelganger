"use client";
import { useEffect, useState } from "react";
import { api, type DistItem, type QuestionResult, type ResultsSummary, type Summary } from "@/lib/api";

export default function RunResults({ runId }: { runId: number }) {
  const [results, setResults] = useState<ResultsSummary | null>(null);
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
  if (!results?.available || results.questions.length === 0) return null;

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-6">
      <h2 className="font-semibold mb-1">Results preview</h2>
      <p className="text-gray-500 text-xs mb-6 leading-relaxed">
        Based on {results.n_completed} AI {results.n_completed === 1 ? "respondent" : "respondents"}
        {results.has_conditions ? ", broken out by condition" : ""}. Directional only — a gut-check
        on whether your design produces a signal, not a substitute for human data.
      </p>

      <div className="flex flex-col divide-y divide-gray-800">
        {results.questions.map((q) => (
          <QuestionBlock key={q.qid} q={q} hasConditions={!!results.has_conditions} />
        ))}
      </div>
    </div>
  );
}

function QuestionBlock({ q, hasConditions }: { q: QuestionResult; hasConditions: boolean }) {
  return (
    <div className="py-5 first:pt-0 last:pb-0">
      <div className="text-sm font-medium text-white mb-3 leading-snug">{q.prompt}</div>

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
            <div className="text-xs text-gray-400 mb-1.5">{c.condition} <span className="text-gray-600">· n={c.n}</span></div>
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
                <th key={cond} className="text-right font-normal pb-2 px-2">{cond}</th>
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
function MeanBar({ label, mean, bounds, n }: { label?: string; mean: number; bounds: Bounds | null; n: number }) {
  const pct = bounds && bounds.max > bounds.min
    ? ((mean - bounds.min) / (bounds.max - bounds.min)) * 100
    : 100;
  return (
    <div className="flex items-center gap-3">
      {label && <div className="w-28 shrink-0 text-xs text-gray-300 truncate" title={label}>{label}</div>}
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
