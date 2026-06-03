"""Aggregate per-session AI responses into a condition-aware results summary.

Reads the artifacts written by the simulator into a run's output directory:
  - survey_meta.json     question metadata (labels, choices, recodes)
  - NNN_<persona>_completed.json   one per completed session, with `answers`

and produces a per-question summary, broken out by experimental condition
(the randomizer branch each session landed in) when conditions are present.
"""
import json
from collections import Counter
from pathlib import Path
from typing import Any


def build_results(out_dir: Path) -> dict[str, Any]:
    meta_path = out_dir / "survey_meta.json"
    if not meta_path.exists():
        return {"available": False, "questions": []}

    meta = json.loads(meta_path.read_text())
    questions_meta = meta.get("questions", [])

    sessions: list[dict] = []
    for jf in sorted(out_dir.glob("*_completed.json")):
        try:
            sessions.append(json.loads(jf.read_text()))
        except Exception:
            continue

    distinct_conditions = sorted(
        {s["branch_description"] for s in sessions if s.get("branch_description")}
    )
    has_conditions = len(distinct_conditions) >= 2

    def condition_of(s: dict) -> str:
        return s.get("branch_description") or "All respondents"

    questions_out: list[dict] = []
    for qm in questions_meta:
        qid = qm["qid"]
        answered = [
            (condition_of(s), (s.get("answers") or {})[qid])
            for s in sessions
            if qid in (s.get("answers") or {})
        ]
        if not answered:
            continue

        q_summary: dict[str, Any] = {
            "qid": qid,
            "prompt": qm.get("prompt") or qid,
            "type": qm["type"],
            "n": len(answered),
            "overall": _summarize(qm, [v for _, v in answered]),
        }
        if has_conditions:
            by_condition = []
            for cond in distinct_conditions:
                vals = [v for c, v in answered if c == cond]
                if vals:
                    by_condition.append({"condition": cond, **_summarize(qm, vals)})
            q_summary["by_condition"] = by_condition

        questions_out.append(q_summary)

    return {
        "available": True,
        "n_completed": len(sessions),
        "has_conditions": has_conditions,
        "conditions": distinct_conditions,
        "questions": questions_out,
    }


def _summarize(qm: dict, values: list[Any]) -> dict[str, Any]:
    qtype = qm.get("type")
    if qtype == "Matrix":
        return _summarize_matrix(qm, values)
    if qtype == "TE":
        return {"kind": "text", "n": len(values), "responses": [str(v) for v in values]}
    if qm.get("multi_select"):
        return _summarize_multi(qm, values)
    return _summarize_single(qm, values)


def _summarize_single(qm: dict, values: list[Any]) -> dict[str, Any]:
    id_to = {c["choice_id"]: c for c in qm.get("choices", [])}
    counts = Counter(str(v) for v in values)
    distribution = [
        {
            "label": id_to.get(cid, {}).get("text", cid),
            "count": n,
            "recode": id_to.get(cid, {}).get("recode"),
        }
        for cid, n in counts.most_common()
    ]
    mean = _maybe_mean([id_to.get(str(v)) for v in values])
    return {"kind": "choice", "n": len(values), "distribution": distribution, "mean": mean}


def _summarize_multi(qm: dict, values: list[Any]) -> dict[str, Any]:
    id_to = {c["choice_id"]: c for c in qm.get("choices", [])}
    flat: list[str] = []
    for v in values:
        if isinstance(v, list):
            flat.extend(str(x) for x in v)
        elif v is not None:
            flat.append(str(v))
    counts = Counter(flat)
    distribution = [
        {
            "label": id_to.get(cid, {}).get("text", cid),
            "count": n,
            "recode": id_to.get(cid, {}).get("recode"),
        }
        for cid, n in counts.most_common()
    ]
    return {"kind": "multi", "n": len(values), "distribution": distribution, "mean": None}


def _summarize_matrix(qm: dict, values: list[Any]) -> dict[str, Any]:
    id_to = {c["choice_id"]: c for c in qm.get("choices", [])}  # scale points
    rows = []
    for sub in qm.get("sub_questions", []):
        sub_id = sub["choice_id"]
        chosen = [str(v[sub_id]) for v in values if isinstance(v, dict) and sub_id in v]
        if not chosen:
            continue
        counts = Counter(chosen)
        rows.append({
            "row": sub["text"],
            "n": len(chosen),
            "mean": _maybe_mean([id_to.get(cid) for cid in chosen]),
            "distribution": [
                {
                    "label": id_to.get(cid, {}).get("text", cid),
                    "count": n,
                    "recode": id_to.get(cid, {}).get("recode"),
                }
                for cid, n in counts.most_common()
            ],
        })
    return {"kind": "matrix", "n": len(values), "rows": rows}


def _maybe_mean(choices: list[dict | None]) -> float | None:
    """Mean of recode values — only when every answered choice has a numeric
    recode. Returns None for categorical questions so we never show a
    meaningless 'average' of, say, gender categories."""
    recodes = []
    for c in choices:
        if not c:
            return None
        r = c.get("recode")
        if isinstance(r, bool) or not isinstance(r, (int, float)):
            return None
        recodes.append(r)
    if not recodes:
        return None
    return round(sum(recodes) / len(recodes), 2)
