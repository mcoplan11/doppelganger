"use client";
import { useMemo } from "react";
import { AgGridReact } from "ag-grid-react";
import { type ColDef } from "ag-grid-community";
import { type RespondentData } from "@/lib/api";
import { gridTheme } from "./gridTheme";

const PINNED = new Set(["model", "persona", "branch"]);
const HEADER_NAMES: Record<string, string> = {
  model: "Model",
  persona: "Persona",
  branch: "Condition",
};

// Respondent-level data grid: one row per simulated respondent per model, with
// every question as a column. Sortable/filterable — the interactive counterpart
// to the CSV download.
export default function RespondentGrid({ data }: { data: RespondentData }) {
  const colDefs = useMemo<ColDef[]>(
    () =>
      data.columns.map((c) => ({
        field: c,
        headerName: HEADER_NAMES[c] ?? c,
        headerTooltip: HEADER_NAMES[c] ?? c,
        pinned: PINNED.has(c) ? ("left" as const) : undefined,
        width: PINNED.has(c) ? 150 : 180,
        tooltipField: c,
      })),
    [data]
  );

  return (
    <>
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
    </>
  );
}
