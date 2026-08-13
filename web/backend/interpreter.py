"""AI results-interpreter.

Turns an ensemble results summary into a plain-language read for the researcher:
a headline, key observations, survey issues to fix before fielding, and an overall
recommendation. Runs as a post-run step and is best-effort — it must NEVER fail a
run (a failure just means no interpretation is attached).

This is an AI-executed decision in production: the model reads the anonymized
per-model response distributions and *decides* what to flag and what to recommend
before the researcher spends money fielding the survey on real people. It runs on
the same backend as the survey responses (Vertex AI when GEMINI_USE_VERTEX is set).

The anonymity contract from ensemble.py holds here too: this module only ever sees
the public labels ("Model A"/"B"/"C"), never real model ids.
"""
from __future__ import annotations

import json
from typing import Any

from app_config import settings

MAX_QUESTIONS = 40          # cap prompt size on long surveys
MAX_PROMPT_CHARS = 160      # truncate each question's stem

INTERPRETATION_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "observations": {"type": "array", "items": {"type": "string"}},
        "issues_to_check": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "concern": {"type": "string"},
                    "suggestion": {"type": "string"},
                },
                "required": ["question", "concern", "suggestion"],
            },
        },
        "recommendation": {"type": "string"},
    },
    "required": ["headline", "observations", "issues_to_check", "recommendation"],
}

_SYSTEM = """You are a survey-methodology expert reviewing a PRETEST run. A panel \
of AI survey respondents (persona-conditioned language models, shown anonymized as \
Model A/B/C) answered the researcher's Qualtrics survey before it is fielded on real \
people. Your job is to help the researcher catch problems now — not to report on the \
AI itself.

Focus on what pretesting is for:
- Manipulation checks: if the survey has randomized CONDITIONS, do responses actually \
differ between conditions where they should? A condition that moves nothing may mean a \
weak manipulation or a wording problem.
- Discrimination: questions where nearly everyone picks the same option (ceiling/floor, \
no variance) may not discriminate between respondents — flag them.
- Matrix straightlining: rows answered almost identically can signal a fatiguing or \
redundant battery.
- Model disagreement: when Models A/B/C diverge sharply on a question, treat that as \
UNCERTAINTY worth a closer human look, not as a finding.
- Branch/condition balance: note lopsided condition sizes.

Rules:
- Refer to models only as "Model A/B/C". Never invent real model names.
- Be concrete and cite the question stem when flagging something.
- Be honest and calibrated: AI respondents are a screening tool, not humans. A pattern \
here is a hypothesis to check, never proof about real respondents. Do NOT overclaim.
- 3-6 observations. 0-5 issues_to_check (only real, actionable ones — empty is fine if \
the survey looks clean). One clear recommendation (e.g. field as-is, or revise X first).
"""


def _fmt_summary(s: dict) -> str:
    kind = s.get("kind")
    if kind in ("choice", "multi"):
        dist = ", ".join(
            f"{d.get('label', '?')}={d.get('count', 0)}"
            for d in s.get("distribution", [])[:6]
        )
        mean = s.get("mean")
        return dist + (f"  (mean {mean})" if mean is not None else "")
    if kind == "matrix":
        parts = []
        for r in s.get("rows", [])[:8]:
            m = r.get("mean")
            n = sum(d.get("count", 0) for d in r.get("distribution", []))
            parts.append(f"{r.get('row', '?')}: mean {m}" if m is not None
                         else f"{r.get('row', '?')}: {n} resp")
        return "; ".join(parts)
    if kind == "text":
        return f"{len(s.get('responses', []))} free-text responses"
    return ""


def _digest(survey_name: str | None, n_participants: int, models: list[dict]) -> str:
    """Compact, token-bounded text view of the ensemble results for the model."""
    live = [m for m in models if (m.get("results") or {}).get("available")]
    lines = [
        f"SURVEY: {survey_name or 'Untitled survey'}",
        f"AI respondents: {n_participants} per model, {len(live)} model(s) "
        f"({', '.join(m['label'] for m in live)}).",
    ]
    conds: list[str] = []
    for m in live:
        c = (m["results"].get("conditions") or [])
        if c:
            conds = c
            break
    if conds:
        lines.append(f"RANDOMIZED CONDITIONS: {', '.join(conds)}")
    # Flag any model that produced no data.
    lost = [m["label"] for m in models if not (m.get("results") or {}).get("available")]
    if lost:
        lines.append(f"NOTE: {', '.join(lost)} produced no data this run.")
    lines.append("")
    lines.append("PER-QUESTION RESPONSE DISTRIBUTIONS:")

    if not live:
        return "\n".join(lines)

    index_qs = live[0]["results"].get("questions", [])
    if len(index_qs) > MAX_QUESTIONS:
        lines.append(f"(showing first {MAX_QUESTIONS} of {len(index_qs)} questions)")
    for q in index_qs[:MAX_QUESTIONS]:
        qid = q["qid"]
        prompt = (q.get("prompt") or qid)[:MAX_PROMPT_CHARS]
        lines.append(f"[{qid}] {prompt}  ({q.get('type')})")
        for m in live:
            mq = next((x for x in m["results"].get("questions", []) if x["qid"] == qid), None)
            if not mq:
                continue
            lines.append(f"   {m['label']}: {_fmt_summary(mq.get('overall', {}))}")
            for c in (mq.get("by_condition") or []):
                if c.get("kind") in ("choice", "multi") and c.get("mean") is not None:
                    lines.append(f"      · {c.get('condition')}: mean {c['mean']}")
    return "\n".join(lines)


def _build_client():
    from google import genai

    if settings.gemini_use_vertex:
        return genai.Client(
            vertexai=True,
            project=settings.gemini_project,
            location=settings.gemini_location,
        )
    return genai.Client(api_key=settings.gemini_api_key)


def generate_interpretation(
    survey_name: str | None, n_participants: int, models: list[dict]
) -> dict[str, Any] | None:
    """Return the interpretation dict, or None if it can't be produced.

    Best-effort: any failure (no live models, API error, bad JSON) returns None
    so the caller can proceed without an interpretation.
    """
    live = [m for m in models if (m.get("results") or {}).get("available")]
    if not live:
        return None
    digest = _digest(survey_name, n_participants, models)
    try:
        from google.genai import types

        client = _build_client()
        resp = client.models.generate_content(
            model=settings.gemini_model,
            contents=f"{_SYSTEM}\n\n=== RESULTS ===\n{digest}\n\nReturn only JSON.",
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=INTERPRETATION_SCHEMA,
                temperature=0.3,
            ),
        )
        data = json.loads(resp.text)
        return data
    except Exception as exc:  # never fail the run over an interpretation
        print(f"[interpreter] non-fatal failure: {exc}", flush=True)
        return None
