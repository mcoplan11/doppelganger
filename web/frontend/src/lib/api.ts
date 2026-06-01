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
  me: () => request<{ id: number; email: string; credits: number }>("/me"),

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
  }) => request<Run>("/runs", { method: "POST", body: JSON.stringify(body) }),

  listRuns: () => request<Run[]>("/runs"),
  getRun: (id: number) => request<Run>(`/runs/${id}`),
  downloadUrl: (id: number) => `${BASE}/runs/${id}/download`,
};

export interface Run {
  id: number;
  original_survey_id: string;
  ai_survey_id: string | null;
  n_participants: number;
  is_smoke_test: boolean;
  status: string;
  credits_used: number;
  error: string | null;
  branch_distribution: Record<string, number>;
  created_at: string;
  completed_at: string | null;
}
