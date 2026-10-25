"use client";
import { useMemo, useRef, useState } from "react";
import { AgGridReact } from "ag-grid-react";
import { type CellStyle, type ColDef, type ColGroupDef } from "ag-grid-community";
import { type RespondentData } from "@/lib/api";
import { gridTheme } from "./gridTheme";

const META_COLS = new Set(["model", "persona", "branch"]);
const SEP = "§"; // field-key separator — never appears in question or model names

const DISAGREE_STYLE: CellStyle = { backgroundColor: "rgba(245, 158, 11, 0.14)" };

type Value = string | number | null;
type PivotRow = Record<string, Value> & { persona: string; branch: Value };

// Cross-model comparison: one row per persona, one column group per question
// with a sub-column per model, so disagreements between Model A/B/C are visible
// at a glance. Cells where the models disagree are highlighted; a pinned
// "Models agree" column scores each respondent across all questions.
export default function ComparisonGrid({ data, runId }: { data: RespondentData; runId: number }) {
  const gridRef = useRef<AgGridReact>(null);
  const [quickFilter, setQuickFilter] = useState("");

  const { rows, colDefs, models } = useMemo(() => buildPivot(data), [data]);

  if (models.length < 2) return null;

  return (
    <>
      <p className="text-gray-500 text-xs mb-3 leading-relaxed">
        One row per simulated respondent, with each question answered by all {models.length} models
        side by side. <span className="text-amber-400/90">Highlighted cells</span> mark questions
        where the models disagree for that respondent — scan them to judge how robust each answer
        is before trusting a pattern.
      </p>
      <div className="flex items-center gap-3 mb-3">
        <input
          value={quickFilter}
          onChange={(e) => setQuickFilter(e.target.value)}
          placeholder="Quick filter — persona, condition, any answer…"
          className="flex-1 bg-gray-950 border border-gray-800 rounded-lg px-3 py-1.5 text-xs text-gray-300 placeholder-gray-600 focus:outline-none focus:border-blue-600"
        />
        <button
          onClick={() =>
            gridRef.current?.api?.exportDataAsCsv({ fileName: `run_${runId}_model_comparison.csv` })
          }
          className="shrink-0 text-xs border border-gray-700 hover:border-gray-500 text-gray-300 rounded-lg px-3 py-1.5 transition"
        >
          Export CSV
        </button>
      </div>
      <div style={{ height: Math.min(600, 180 + rows.length * 36) }}>
        <AgGridReact
          ref={gridRef}
          theme={gridTheme}
          rowData={rows}
          columnDefs={colDefs}
          defaultColDef={{ sortable: true, filter: true, resizable: true }}
          quickFilterText={quickFilter}
          pagination={rows.length > 50}
          paginationPageSize={50}
          tooltipShowDelay={300}
        />
      </div>
    </>
  );
}

function buildPivot(data: RespondentData): {
  rows: PivotRow[];
  colDefs: (ColDef | ColGroupDef)[];
  models: string[];
} {
  const models = [...new Set(data.rows.map((r) => String(r.model ?? "")))].filter(Boolean);
  const questions = data.columns.filter((c) => !META_COLS.has(c));

  // persona+branch → one pivot row holding every model's answer per question.
  const byKey = new Map<string, PivotRow>();
  for (const r of data.rows) {
    const key = `${r.persona}||${r.branch}`;
    let row = byKey.get(key);
    if (!row) {
      row = { persona: String(r.persona ?? ""), branch: r.branch ?? null };
      byKey.set(key, row);
    }
    for (const q of questions) row[`${q}${SEP}${r.model}`] = r[q] ?? null;
  }
  const rows = [...byKey.values()];

  // Free-text columns are expected to differ between models — don't score them.
  const scoredQuestions = questions.filter((q) => !isFreeText(q, rows, models));

  for (const row of rows) {
    let agreed = 0;
    for (const q of scoredQuestions) {
      const agree = modelsAgree(models.map((m) => row[`${q}${SEP}${m}`]));
      row[`${q}${SEP}__agree`] = agree ? 1 : 0;
      if (agree) agreed += 1;
    }
    row.__agreement = scoredQuestions.length ? agreed / scoredQuestions.length : 1;
    row.__agreementLabel = `${agreed}/${scoredQuestions.length}`;
  }

  const colDefs: (ColDef | ColGroupDef)[] = [
    { field: "persona", headerName: "Persona", pinned: "left", width: 160, tooltipField: "persona" },
    { field: "branch", headerName: "Condition", pinned: "left", width: 170, tooltipField: "branch" },
    {
      field: "__agreementLabel",
      headerName: "Agree",
      headerTooltip: "Questions where all models gave a matching answer for this respondent",
      pinned: "left",
      width: 110,
      comparator: (a, b, nodeA, nodeB) =>
        Number(nodeA.data?.__agreement ?? 0) - Number(nodeB.data?.__agreement ?? 0),
      cellStyle: (p): CellStyle =>
        Number(p.data?.__agreement ?? 1) < 0.75
          ? { color: "#fbbf24", fontWeight: 600 }
          : { color: "#4ade80", fontWeight: 400 },
    },
    ...questions.map((q): ColGroupDef => {
      const scored = scoredQuestions.includes(q);
      return {
        headerName: q,
        headerTooltip: q,
        children: models.map((m, i) => ({
          field: `${q}${SEP}${m}`,
          headerName: m.replace(/^Model\s+/, ""),
          headerTooltip: `${q} — ${m}`,
          columnGroupShow: (i === 0 ? undefined : "open") as "open" | undefined,
          width: scored ? 90 : 200,
          tooltipField: `${q}${SEP}${m}`,
          cellStyle: scored
            ? (p) => (p.data?.[`${q}${SEP}__agree`] === 0 ? DISAGREE_STYLE : null)
            : undefined,
        })),
        openByDefault: true,
      };
    }),
  ];

  return { rows, colDefs, models };
}

// A column is free text when most values are unique strings — per-model prose
// never matches exactly, so highlighting it as "disagreement" would be noise.
function isFreeText(q: string, rows: PivotRow[], models: string[]): boolean {
  const values: string[] = [];
  for (const row of rows)
    for (const m of models) {
      const v = row[`${q}${SEP}${m}`];
      if (v != null && v !== "") values.push(String(v));
    }
  if (values.length === 0) return false;
  if (values.every((v) => isNumeric(v))) return false;
  const distinct = new Set(values).size;
  return distinct / values.length > 0.6 || values.some((v) => v.length > 60);
}

function modelsAgree(values: Value[]): boolean {
  const present = values.filter((v) => v != null && v !== "");
  if (present.length < 2) return true;
  if (present.every((v) => isNumeric(v))) {
    const nums = present.map(Number);
    // Adjacent scale points (e.g. 5 vs 6 on a 7-point Likert) count as agreement;
    // only a gap of 2+ is a substantive disagreement.
    return Math.max(...nums) - Math.min(...nums) <= 1;
  }
  return new Set(present.map(String)).size === 1;
}

function isNumeric(v: Value): boolean {
  if (typeof v === "number") return Number.isFinite(v);
  return typeof v === "string" && v.trim() !== "" && !Number.isNaN(Number(v));
}
