"use client";
import { useEffect, useMemo, useState } from "react";
import { AgGridReact } from "ag-grid-react";
import {
  AllCommunityModule,
  ModuleRegistry,
  colorSchemeDark,
  themeQuartz,
  type ColDef,
} from "ag-grid-community";
import { api, type RespondentData } from "@/lib/api";

ModuleRegistry.registerModules([AllCommunityModule]);

// Match the app's Tailwind gray-950 dark palette.
const gridTheme = themeQuartz.withPart(colorSchemeDark).withParams({
  backgroundColor: "#030712", // gray-950
  headerBackgroundColor: "#111827", // gray-900
  borderColor: "#1f2937", // gray-800
  textColor: "#d1d5db", // gray-300
  headerTextColor: "#9ca3af", // gray-400
  accentColor: "#3b82f6", // blue-500
  fontSize: 12,
});

const PINNED = new Set(["model", "persona", "branch"]);
const HEADER_NAMES: Record<string, string> = {
  model: "Model",
  persona: "Persona",
  branch: "Condition",
};

// Respondent-level data grid: one row per simulated respondent per model, with
// every question as a column. Sortable/filterable — the interactive counterpart
// to the CSV download. Renders nothing while loading or when the backend no
// longer has the per-session files (available: false).
export default function RespondentGrid({ runId }: { runId: number }) {
  const [data, setData] = useState<RespondentData | null>(null);

  useEffect(() => {
    api.getResponses(runId).then(setData).catch(() => setData(null));
  }, [runId]);

  const colDefs = useMemo<ColDef[]>(() => {
    if (!data) return [];
    return data.columns.map((c) => ({
      field: c,
      headerName: HEADER_NAMES[c] ?? c,
      headerTooltip: HEADER_NAMES[c] ?? c,
      pinned: PINNED.has(c) ? ("left" as const) : undefined,
      width: PINNED.has(c) ? 150 : 180,
      tooltipField: c,
    }));
  }, [data]);

  if (!data?.available || data.rows.length === 0) return null;

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-6">
      <h2 className="font-semibold mb-1">Respondent-level data</h2>
      <p className="text-gray-500 text-xs mb-4 leading-relaxed">
        One row per simulated respondent per model ({data.rows.length} rows). Sort or filter any
        column to explore — this is the same data as the CSV download.
      </p>
      <div style={{ height: Math.min(600, 140 + data.rows.length * 36) }}>
        <AgGridReact
          theme={gridTheme}
          rowData={data.rows}
          columnDefs={colDefs}
          defaultColDef={{ sortable: true, filter: true, resizable: true }}
          pagination={data.rows.length > 50}
          paginationPageSize={50}
          tooltipShowDelay={300}
        />
      </div>
    </div>
  );
}
