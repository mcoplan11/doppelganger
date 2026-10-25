"use client";
import { useEffect, useMemo, useState } from "react";
import { api, type RespondentData } from "@/lib/api";
import RespondentGrid from "./RespondentGrid";
import ComparisonGrid from "./ComparisonGrid";

type View = "comparison" | "respondents";

// Container for the respondent-level grids: fetches /responses once and offers
// two AG Grid views — the cross-model comparison (default when the run used an
// ensemble) and the flat one-row-per-respondent table.
export default function ResponseExplorer({ runId }: { runId: number }) {
  const [data, setData] = useState<RespondentData | null>(null);

  useEffect(() => {
    api.getResponses(runId).then(setData).catch(() => setData(null));
  }, [runId]);

  const modelCount = useMemo(
    () => new Set((data?.rows ?? []).map((r) => r.model).filter(Boolean)).size,
    [data]
  );
  const hasComparison = modelCount >= 2;
  const [view, setView] = useState<View | null>(null);
  const activeView: View = view ?? (hasComparison ? "comparison" : "respondents");

  if (!data?.available || data.rows.length === 0) return null;

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-6">
      <div className="flex items-center justify-between mb-1">
        <h2 className="font-semibold">Respondent-level data</h2>
        {hasComparison && (
          <div className="flex rounded-lg border border-gray-700 overflow-hidden text-xs">
            {(
              [
                ["comparison", "Compare models"],
                ["respondents", "By respondent"],
              ] as [View, string][]
            ).map(([v, label]) => (
              <button
                key={v}
                onClick={() => setView(v)}
                className={`px-3 py-1.5 font-medium transition-colors ${
                  activeView === v
                    ? "bg-blue-600 text-white"
                    : "bg-gray-800 text-gray-400 hover:text-gray-200"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        )}
      </div>
      {activeView === "comparison" && hasComparison ? (
        <ComparisonGrid data={data} runId={runId} />
      ) : (
        <RespondentGrid data={data} />
      )}
    </div>
  );
}
