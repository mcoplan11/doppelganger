#!/usr/bin/env python3
"""
Convert raw JSON results to annotated CSV files.

Each CSV includes:
  - persona identifier
  - condition / item context
  - the exact question text shown to the AI
  - the AI's answer (raw ID + human-readable text)
  - the expected effect from the original paper
  - the paper's replication result

Usage:
    python export_csvs.py results/20260607_173525/
    python export_csvs.py results/20260607_173525/ --out-dir my_csvs/
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent


def load_experiments(path: Path) -> dict[str, dict]:
    return {e["id"]: e for e in json.loads(path.read_text())}


def _choice_text(options: list[dict], choice_id) -> str:
    if choice_id is None:
        return ""
    for opt in options:
        if str(opt["id"]) == str(choice_id):
            return opt["text"]
    return str(choice_id)


def _paper_result_label(result: str) -> str:
    return {"replicated": "Replicated", "not_replicated": "Not replicated",
            "partial": "Partial replication"}.get(result, result)


# ── Per-experiment CSV writers ────────────────────────────────────────────────

def export_between(exp: dict, rows: list[dict], out_path: Path) -> None:
    """Between-subject (and within-run-as-between) experiments."""
    cond_map = {c["id"]: c for c in exp["conditions"]}
    paper_result = _paper_result_label(exp.get("paper_result", ""))
    expected = exp.get("analysis", {}).get("description", "")

    with open(out_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "experiment_id", "experiment_name", "citation",
            "paper_result", "expected_effect",
            "persona",
            "condition_id", "condition_name",
            "scenario", "question",
            "response_type",
            "answer_raw", "answer_text",
            "error",
        ])
        for row in rows:
            cid = row.get("condition_id", "")
            cond = cond_map.get(cid, {})
            options = cond.get("options", [])
            answer_raw = row.get("answer")
            answer_text = (_choice_text(options, answer_raw)
                           if cond.get("response_type") == "choice"
                           else str(answer_raw) if answer_raw is not None else "")
            writer.writerow([
                exp["id"], exp["name"], exp.get("citation", ""),
                paper_result, expected,
                row.get("persona", ""),
                cid, cond.get("name", cid),
                cond.get("scenario", ""), cond.get("question", ""),
                cond.get("response_type", ""),
                answer_raw, answer_text,
                row.get("error") or "",
            ])


def export_false_consensus(exp: dict, rows: list[dict], out_path: Path) -> None:
    items_map = {it["id"]: it for it in exp.get("items", [])}
    paper_result = _paper_result_label(exp.get("paper_result", ""))
    expected = exp.get("analysis", {}).get("description", "")

    with open(out_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "experiment_id", "experiment_name", "citation",
            "paper_result", "expected_effect",
            "persona",
            "item_id", "item_description",
            "own_question", "own_view_rating",
            "public_question", "public_estimate_pct",
            "error",
        ])
        for row in rows:
            item = items_map.get(row.get("item_id", ""), {})
            writer.writerow([
                exp["id"], exp["name"], exp.get("citation", ""),
                paper_result, expected,
                row.get("persona", ""),
                row.get("item_id", ""), item.get("description", ""),
                item.get("own_question", ""), row.get("own_view"),
                item.get("public_question", ""), row.get("public_estimate"),
                row.get("error") or "",
            ])


def export_risk_benefit(exp: dict, rows: list[dict], out_path: Path) -> None:
    paper_result = _paper_result_label(exp.get("paper_result", ""))
    expected = exp.get("analysis", {}).get("description", "")
    risk_q_template = exp.get("risk_question", "")
    benefit_q_template = exp.get("benefit_question", "")
    scale = "1 (Very low) – 7 (Very high)"

    with open(out_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "experiment_id", "experiment_name", "citation",
            "paper_result", "expected_effect",
            "persona",
            "item_id", "item_label",
            "risk_question", "risk_rating",
            "benefit_question", "benefit_rating",
            "scale",
            "error",
        ])
        for row in rows:
            label = row.get("item_label", row.get("item_id", ""))
            writer.writerow([
                exp["id"], exp["name"], exp.get("citation", ""),
                paper_result, expected,
                row.get("persona", ""),
                row.get("item_id", ""), label,
                risk_q_template.replace("{label}", label),
                row.get("risk_rating"),
                benefit_q_template.replace("{label}", label),
                row.get("benefit_rating"),
                scale,
                row.get("error") or "",
            ])


def export_omission_bias(exp: dict, rows: list[dict], out_path: Path) -> None:
    cond_map = {c["id"]: c for c in exp.get("conditions", [])}
    paper_result = _paper_result_label(exp.get("paper_result", ""))
    expected = exp.get("analysis", {}).get("description", "")

    with open(out_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "experiment_id", "experiment_name", "citation",
            "paper_result", "expected_effect",
            "persona",
            "condition_id", "condition_name",
            "scenario", "question",
            "answer_raw", "answer_text",
            "error",
        ])
        for row in rows:
            cid = row.get("condition_id", "")
            cond = cond_map.get(cid, {})
            options = cond.get("options", [])
            answer_raw = row.get("answer")
            answer_text = _choice_text(options, answer_raw) if options else str(answer_raw or "")
            writer.writerow([
                exp["id"], exp["name"], exp.get("citation", ""),
                paper_result, expected,
                row.get("persona", ""),
                cid, cond.get("name", cid),
                cond.get("scenario", ""), cond.get("question", ""),
                answer_raw, answer_text,
                row.get("error") or "",
            ])


def export_single_condition(exp: dict, rows: list[dict], out_path: Path) -> None:
    """Probability matching and dominator neglect."""
    cond = exp["conditions"][0]
    options = cond.get("options", [])
    paper_result = _paper_result_label(exp.get("paper_result", ""))
    expected = exp.get("analysis", {}).get("description", "")

    with open(out_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "experiment_id", "experiment_name", "citation",
            "paper_result", "expected_effect",
            "persona",
            "scenario", "question",
            "response_type",
            "answer_raw", "answer_text",
            "error",
        ])
        for row in rows:
            answer_raw = row.get("answer")
            answer_text = (_choice_text(options, answer_raw)
                           if options else str(answer_raw or ""))
            writer.writerow([
                exp["id"], exp["name"], exp.get("citation", ""),
                paper_result, expected,
                row.get("persona", ""),
                cond.get("scenario", ""), cond.get("question", ""),
                cond.get("response_type", ""),
                answer_raw, answer_text,
                row.get("error") or "",
            ])


SINGLE_CONDITION_IDS = {"probability_matching", "dominator_neglect"}


def export_experiment(exp: dict, rows: list[dict], out_dir: Path) -> Path:
    out_path = out_dir / f"{exp['id']}.csv"
    analysis_type = exp.get("analysis", {}).get("type", "")

    if analysis_type == "false_consensus_correlation":
        export_false_consensus(exp, rows, out_path)
    elif analysis_type == "within_correlation":
        export_risk_benefit(exp, rows, out_path)
    elif exp["id"] == "omission_bias":
        export_omission_bias(exp, rows, out_path)
    elif exp["id"] in SINGLE_CONDITION_IDS:
        export_single_condition(exp, rows, out_path)
    else:
        export_between(exp, rows, out_path)

    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Export JSON results to annotated CSVs")
    parser.add_argument("results_dir", help="Path to a results/YYYYMMDD_HHMMSS/ directory")
    parser.add_argument("--out-dir", help="Output directory (default: <results_dir>/csv/)")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    out_dir = Path(args.out_dir) if args.out_dir else results_dir / "csv"
    out_dir.mkdir(parents=True, exist_ok=True)

    experiments = load_experiments(HERE / "experiments.json")

    exported = []
    for exp_id, exp in experiments.items():
        json_path = results_dir / f"{exp_id}.json"
        if not json_path.exists():
            print(f"  [skip] {exp_id}.json not found")
            continue
        rows = json.loads(json_path.read_text())
        out_path = export_experiment(exp, rows, out_dir)
        print(f"  ✓ {out_path.name}  ({len(rows)} rows)")
        exported.append(out_path)

    print(f"\n{len(exported)} CSV files written to: {out_dir}")


if __name__ == "__main__":
    main()
