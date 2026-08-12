const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  // Auth
  requestMagicLink: (email: string) =>
    request("/auth/request", { method: "POST", body: JSON.stringify({ email }) }),
  logout: () => request("/auth/logout", { method: "POST" }),

  // Me
  me: () => request<{ id: number; email: string; credits: number; qualtrics_token: string | null; qualtrics_datacenter: string | null }>("/me"),

  // Credits
  packs: () =>
    request<{ id: string; credits: number; price_cents: number; label: string; per: string }[]>(
      "/credits/packs"
    ),
  checkout: (pack_id: string) =>
    request<{ checkout_url: string }>("/credits/checkout", {
      method: "POST",
      body: JSON.stringify({ pack_id }),
    }),

  // Runs
  createRun: (body: {
    survey_url: string;
    qualtrics_token: string;
    qualtrics_datacenter?: string;
    n_participants: number;
    smoke_test?: boolean;
    platform?: string;
  }) => request<Run>("/runs", { method: "POST", body: JSON.stringify(body) }),

  listRuns: () => request<Run[]>("/runs"),
  getRun: (id: number) => request<Run>(`/runs/${id}`),
  getResults: (id: number) => request<ResultsSummary | EnsembleResults>(`/runs/${id}/results`),
  cancelRun: (id: number) => request<Run>(`/runs/${id}/cancel`, { method: "POST" }),
  downloadUrl: (id: number) => `${BASE}/runs/${id}/download`,
};

export interface AiSurveyCopy {
  slug: string;
  label: string;            // anonymized: "Model A" / "Model B" / …
  ai_survey_id: string | null;
}

export interface Run {
  id: number;
  original_survey_id: string;
  ai_survey_id: string | null;
  ai_survey_copies?: AiSurveyCopy[];   // one Qualtrics copy per ensemble model
  n_participants: number;
  is_smoke_test: boolean;
  platform: string;
  status: string;
  credits_used: number;
  error: string | null;
  branch_distribution: Record<string, number>;
  created_at: string;
  completed_at: string | null;
}

export interface DistItem {
  label: string;
  count: number;
  recode: number | null;
}

export interface MatrixRow {
  row: string;
  n: number;
  mean: number | null;
  distribution: DistItem[];
}

export interface Summary {
  kind: "choice" | "multi" | "text" | "matrix";
  n: number;
  mean?: number | null;
  distribution?: DistItem[];
  responses?: string[];
  rows?: MatrixRow[];
}

export type ConditionSummary = Summary & { condition: string };

export interface QuestionResult {
  qid: string;
  prompt: string;
  type: string;
  n: number;
  overall: Summary;
  by_condition?: ConditionSummary[];
}

export interface ResultsSummary {
  available: boolean;
  n_completed?: number;
  has_conditions?: boolean;
  conditions?: string[];
  questions: QuestionResult[];
}

// One member of the model ensemble. `label` is anonymized (Model A/B/C); the
// real underlying LLM is never sent to the client.
export interface ModelResult {
  label: string;
  slug: string;
  ai_survey_id: string | null;
  n_completed: number;
  failed: number;
  error: string | null;
  results: ResultsSummary;
}

export interface EnsembleResults {
  ensemble: true;
  n_completed: number;
  models: ModelResult[];
}

export function isEnsembleResults(
  r: ResultsSummary | EnsembleResults | null
): r is EnsembleResults {
  return !!r && (r as EnsembleResults).ensemble === true;
}
