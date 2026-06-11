"""Runs heuristics-and-biases experiments using batch LLM calls."""
from __future__ import annotations

import random
import sys
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from personas import DEFAULT_PERSONAS, Persona

from llm_client import LLMClient


# ── Prompt / schema builders ──────────────────────────────────────────────────

def _build_prompt(
    persona: Persona,
    scenario: str,
    question: str,
    options: list[dict] | None,
    scale: dict | None,
    response_type: str,
) -> str:
    lines = [
        "You are responding to a Qualtrics survey, staying fully in character as this persona:",
        "",
        f"PERSONA: {persona.name}",
        persona.description,
        "",
        "Answer as this persona would — with their biases, blind spots, and rhythm. "
        "Do not be artificially neutral or balanced.",
        "",
    ]
    if scenario:
        lines += ["SCENARIO:", scenario, ""]
    lines += ["QUESTION:", question, ""]
    if response_type == "choice" and options:
        lines.append("OPTIONS:")
        for opt in options:
            lines.append(f"  {opt['id']}: {opt['text']}")
        lines.append("")
        lines.append(f"Return JSON: {{\"answer\": \"<one of {[o['id'] for o in options]}>\"}}")
    elif response_type == "scale" and scale:
        lines.append(
            f"SCALE: {scale['min']} ({scale['min_label']}) "
            f"to {scale['max']} ({scale['max_label']})"
        )
        lines.append("")
        lines.append(
            f"Return JSON: {{\"answer\": <integer from {scale['min']} to {scale['max']}>}}"
        )
    elif response_type == "numeric":
        lines.append("Return JSON: {\"answer\": <number>}")
    return "\n".join(lines)


def _schema_for(
    response_type: str, options: list[dict] | None, scale: dict | None
) -> dict:
    if response_type == "choice" and options:
        return {
            "type": "object",
            "properties": {"answer": {"type": "string", "enum": [o["id"] for o in options]}},
            "required": ["answer"],
        }
    if response_type == "scale" and scale:
        return {
            "type": "object",
            "properties": {
                "answer": {"type": "integer", "minimum": scale["min"], "maximum": scale["max"]}
            },
            "required": ["answer"],
        }
    return {
        "type": "object",
        "properties": {"answer": {"type": "number"}},
        "required": ["answer"],
    }


def _req(key: str, persona: Persona, condition: dict) -> dict:
    """Build a single batch request dict for a (persona, condition) pair."""
    return {
        "key": key,
        "prompt": _build_prompt(
            persona=persona,
            scenario=condition.get("scenario", ""),
            question=condition["question"],
            options=condition.get("options"),
            scale=condition.get("scale"),
            response_type=condition["response_type"],
        ),
        "schema": _schema_for(
            condition["response_type"],
            condition.get("options"),
            condition.get("scale"),
        ),
    }


def _req_scale(key: str, persona: Persona, question: str, scale: dict, scenario: str = "") -> dict:
    cond = {"question": question, "scale": scale, "response_type": "scale", "scenario": scenario}
    return _req(key, persona, cond)


def _req_numeric(key: str, persona: Persona, question: str, scenario: str = "") -> dict:
    cond = {"question": question, "response_type": "numeric", "scenario": scenario}
    return _req(key, persona, cond)


def _extract(raw: dict[str, Any | None], key: str) -> Any:
    result = raw.get(key)
    if result is None:
        return None
    return result.get("answer")


# ── Per-experiment batch runners ──────────────────────────────────────────────

def run_between(
    exp: dict,
    personas: list[Persona],
    llm: LLMClient,
    mode: str,
    seed: int,
    out_dir: Optional[Path] = None,
) -> list[dict]:
    conditions = exp["conditions"]

    if mode == "between":
        rng = random.Random(seed)
        shuffled = list(personas)
        rng.shuffle(shuffled)
        assignments = [
            (persona, conditions[i % len(conditions)])
            for i, persona in enumerate(shuffled)
        ]
    else:  # within: every persona sees every condition
        assignments = [
            (persona, cond) for persona in personas for cond in conditions
        ]

    # Build all requests upfront
    requests = [
        _req(f"{persona.name}::{cond['id']}", persona, cond)
        for persona, cond in assignments
    ]
    cp = str(out_dir / f"{exp['id']}.checkpoint.json") if out_dir else None
    print(f"  Batching {len(requests)} requests...", flush=True)
    raw = llm.complete_batch(requests, checkpoint_path=cp)

    rows = []
    for (persona, cond), req in zip(assignments, requests):
        answer = _extract(raw, req["key"])
        rows.append({
            "experiment_id": exp["id"],
            "persona": persona.name,
            "condition_id": cond["id"],
            "condition_name": cond["name"],
            "answer": answer,
            "error": None if answer is not None else "no response",
        })
    return rows


def run_false_consensus(
    exp: dict, personas: list[Persona], llm: LLMClient, out_dir: Optional[Path] = None,
) -> list[dict]:
    scale_5 = {"min": 1, "max": 5, "min_label": "Strongly disagree", "max_label": "Strongly agree"}
    items = exp["items"]

    requests = []
    meta = []  # (persona, item) pairs matching request order
    for persona in personas:
        for item in items:
            own_key = f"{persona.name}::{item['id']}::own"
            pub_key = f"{persona.name}::{item['id']}::public"
            requests.append(_req_scale(own_key, persona, item["own_question"], scale_5))
            requests.append(_req_numeric(pub_key, persona, item["public_question"]))
            meta.append((persona, item, own_key, pub_key))

    cp = str(out_dir / f"{exp['id']}.checkpoint.json") if out_dir else None
    print(f"  Batching {len(requests)} requests...", flush=True)
    raw = llm.complete_batch(requests, checkpoint_path=cp)

    rows = []
    for persona, item, own_key, pub_key in meta:
        own = _extract(raw, own_key)
        pub = _extract(raw, pub_key)
        rows.append({
            "experiment_id": exp["id"],
            "persona": persona.name,
            "item_id": item["id"],
            "own_view": own,
            "public_estimate": pub,
            "error": None if (own is not None and pub is not None) else "no response",
        })
    return rows


def run_risk_benefit(
    exp: dict, personas: list[Persona], llm: LLMClient, out_dir: Optional[Path] = None,
) -> list[dict]:
    scale_7 = {"min": 1, "max": 7, "min_label": "Very low", "max_label": "Very high"}
    items = exp["items"]

    requests = []
    meta = []
    for persona in personas:
        for item in items:
            risk_q = exp["risk_question"].replace("{label}", item["label"])
            benefit_q = exp["benefit_question"].replace("{label}", item["label"])
            risk_key = f"{persona.name}::{item['id']}::risk"
            benefit_key = f"{persona.name}::{item['id']}::benefit"
            requests.append(_req_scale(risk_key, persona, risk_q, scale_7))
            requests.append(_req_scale(benefit_key, persona, benefit_q, scale_7))
            meta.append((persona, item, risk_key, benefit_key))

    cp = str(out_dir / f"{exp['id']}.checkpoint.json") if out_dir else None
    print(f"  Batching {len(requests)} requests...", flush=True)
    raw = llm.complete_batch(requests, checkpoint_path=cp)

    rows = []
    for persona, item, risk_key, benefit_key in meta:
        risk = _extract(raw, risk_key)
        benefit = _extract(raw, benefit_key)
        rows.append({
            "experiment_id": exp["id"],
            "persona": persona.name,
            "item_id": item["id"],
            "item_label": item["label"],
            "risk_rating": risk,
            "benefit_rating": benefit,
            "error": None if (risk is not None and benefit is not None) else "no response",
        })
    return rows


def run_single_condition(
    exp: dict, personas: list[Persona], llm: LLMClient, out_dir: Optional[Path] = None,
) -> list[dict]:
    """For within-subject experiments that have exactly one condition per persona."""
    cond = exp["conditions"][0]
    requests = [_req(persona.name, persona, cond) for persona in personas]
    cp = str(out_dir / f"{exp['id']}.checkpoint.json") if out_dir else None
    print(f"  Batching {len(requests)} requests...", flush=True)
    raw = llm.complete_batch(requests, checkpoint_path=cp)

    rows = []
    for persona, req in zip(personas, requests):
        answer = _extract(raw, req["key"])
        rows.append({
            "experiment_id": exp["id"],
            "persona": persona.name,
            "answer": answer,
            "error": None if answer is not None else "no response",
        })
    return rows


def run_omission_bias(
    exp: dict, personas: list[Persona], llm: LLMClient, out_dir: Optional[Path] = None,
) -> list[dict]:
    """Within-subject: each persona sees both conditions."""
    conditions = exp["conditions"]
    requests = [
        _req(f"{persona.name}::{cond['id']}", persona, cond)
        for persona in personas
        for cond in conditions
    ]
    cp = str(out_dir / f"{exp['id']}.checkpoint.json") if out_dir else None
    print(f"  Batching {len(requests)} requests...", flush=True)
    raw = llm.complete_batch(requests, checkpoint_path=cp)

    rows = []
    for persona in personas:
        for cond in conditions:
            key = f"{persona.name}::{cond['id']}"
            answer = _extract(raw, key)
            rows.append({
                "experiment_id": exp["id"],
                "persona": persona.name,
                "condition_id": cond["id"],
                "answer": answer,
                "error": None if answer is not None else "no response",
            })
    return rows


# ── Dispatcher ────────────────────────────────────────────────────────────────

def run_experiment(
    exp: dict,
    personas: list[Persona],
    llm: LLMClient,
    between_subject_mode: str,
    seed: int,
    out_dir: Optional[Path] = None,
) -> list[dict]:
    analysis_type = exp.get("analysis", {}).get("type", "")
    print(f"\n[{exp['id']}] {exp['name']} ({exp.get('type', 'between')})", flush=True)

    if analysis_type == "false_consensus_correlation":
        return run_false_consensus(exp, personas, llm, out_dir)
    if analysis_type == "within_correlation":
        return run_risk_benefit(exp, personas, llm, out_dir)
    if exp["id"] == "omission_bias":
        return run_omission_bias(exp, personas, llm, out_dir)
    if analysis_type in ("proportion_matching", "proportion_dominated"):
        return run_single_condition(exp, personas, llm, out_dir)
    return run_between(exp, personas, llm, between_subject_mode, seed, out_dir)


def select_personas(n: int | str, seed: int) -> list[Persona]:
    personas = list(DEFAULT_PERSONAS)
    if n == "all":
        return personas
    n = int(n)
    rng = random.Random(seed)
    return rng.sample(personas, min(n, len(personas)))
