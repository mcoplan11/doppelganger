from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from config import load_config
from gemini_client import GeminiClient
from personas import DEFAULT_PERSONAS, get_persona
from qualtrics_client import QualtricsClient, SurveyDefinition
from simulator import run_many, summarize_run


def cmd_inspect(survey: SurveyDefinition) -> None:
    print(f"Survey: {survey.name} ({survey.survey_id})")
    print(f"Questions: {len(survey.questions)}")
    print(f"Randomizer branches: {len(survey.branches)}")
    for b in survey.branches:
        print(f"  - {b.branch_id}: {b.description}  ({len(b.block_ids)} block(s))")
    print()
    for q in survey.questions:
        branch = survey.branch_for_qid(q.qid)
        branch_tag = f"  [branch: {branch}]" if branch else ""
        print(f"[{q.qid}] {q.question_type}/{q.selector}  tag={q.export_tag}{branch_tag}")
        if q.prompt_text:
            print(f"    {q.prompt_text}")
        for c in q.choices:
            print(f"      - {c.choice_id} (recode={c.recode}): {c.text}")
        for s in q.sub_questions:
            print(f"      row {s.choice_id}: {s.text}")
        print()


def cmd_run(args, qualtrics: QualtricsClient, gemini: GeminiClient, survey: SurveyDefinition) -> None:
    if args.personas:
        personas = [get_persona(name) for name in args.personas]
    elif args.n_personas:
        personas = list(DEFAULT_PERSONAS)[:args.n_personas]
    else:
        personas = list(DEFAULT_PERSONAS)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    use_batch: bool | None = None
    if getattr(args, "batch", False):
        use_batch = True
    elif getattr(args, "no_batch", False):
        use_batch = False
    runs = run_many(
        qualtrics=qualtrics,
        gemini=gemini,
        survey=survey,
        personas=personas,
        runs_per_persona=args.runs,
        out_dir=out_dir,
        use_batch=use_batch,
    )

    print("\n" + "=" * 60)
    completed = [r for r in runs if r.completed]
    failed = [r for r in runs if not r.completed]
    print(f"FINISHED. {len(runs)} sessions: {len(completed)} completed, {len(failed)} failed.")
    if survey.branches and completed:
        branch_counts = Counter(r.branch_description for r in completed)
        print("Branch distribution (informational — Qualtrics decides):")
        for desc, n in branch_counts.items():
            print(f"  {desc}: {n}")
    print("=" * 60)


def main() -> int:
    parser = argparse.ArgumentParser(description="Have AI personas take your Qualtrics survey.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("inspect", help="Print the survey structure (no AI calls).")

    run = sub.add_parser("run", help="Have AI personas take the survey via the Sessions API.")
    run.add_argument("--personas", nargs="*", help="Persona names to use (default: all).")
    run.add_argument("--n-personas", type=int, default=None,
                     help="Use the first N personas from the roster. Ignored if --personas given.")
    run.add_argument(
        "--runs", type=int, default=1,
        help="Runs per persona (default: 1). Total sessions = personas × runs.",
    )
    run.add_argument("--out-dir", default="responses", help="Where to save JSON artifacts.")
    run.add_argument(
        "--temperature", type=float, default=0.5,
        help="Gemini sampling temperature (default: 0.5, validated 2026-05-21 against Ed+Selin). Lower = more deterministic.",
    )
    batch_group = run.add_mutually_exclusive_group()
    batch_group.add_argument(
        "--batch", action="store_true",
        help="Force Gemini Batch API (50%% cost, slower per-round). "
             "Default: auto — batch when total sessions > 20."
    )
    batch_group.add_argument(
        "--no-batch", action="store_true",
        help="Force per-call sync mode (fast feedback, full cost). "
             "Default: auto — sync when total sessions <= 20."
    )
    run.add_argument(
        "--survey-id", default=None,
        help="Override QUALTRICS_SURVEY_ID from .env (useful when comparing surveys).",
    )

    args = parser.parse_args()
    cfg = load_config()
    qualtrics = QualtricsClient(cfg.qualtrics_base_url, cfg.qualtrics_token)
    survey_id = getattr(args, "survey_id", None) or cfg.qualtrics_survey_id
    survey = qualtrics.get_survey_definition(survey_id)

    if args.cmd == "inspect":
        cmd_inspect(survey)
        return 0
    if args.cmd == "run":
        gemini = GeminiClient(
            cfg.gemini_api_key,
            cfg.gemini_model,
            temperature=args.temperature,
            use_vertex=cfg.gemini_use_vertex,
            project=cfg.gemini_project,
            location=cfg.gemini_location,
        )
        cmd_run(args, qualtrics, gemini, survey)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
