#!/usr/bin/env python3
"""
Entry point for the Twin-2K-500 replication experiment.

Usage:
    python run.py                              # run all experiments
    python run.py --experiment framing         # run one experiment by ID
    python run.py --config my_config.yaml      # use a different config
    python run.py --analyze results/20250607_123456/  # analyze existing results
    python run.py --list                       # list all experiment IDs
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
from datetime import datetime
from pathlib import Path

socket.setdefaulttimeout(120)  # prevent hanging API calls from blocking forever

import yaml

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from analysis import analyze_experiment, print_comparison_table, save_detailed_report
from llm_client import build_client
from runner import run_experiment, select_personas


def load_config(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def load_experiments(path: Path) -> list[dict]:
    with open(path) as f:
        return json.load(f)


def resolve_api_key(provider: str) -> str:
    env_map = {
        "gemini": "GEMINI_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
    }
    env_var = env_map.get(provider)
    if not env_var:
        raise ValueError(f"Unknown provider: {provider}")

    # Try loading from parent .env file if not already set
    key = os.environ.get(env_var)
    if not key:
        env_file = HERE.parents[1] / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if line.startswith(env_var + "="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not key:
        raise RuntimeError(
            f"{env_var} not set. Add it to your .env file or export it as an environment variable."
        )
    return key


def main() -> None:
    parser = argparse.ArgumentParser(description="Twin-2K-500 replication runner")
    parser.add_argument("--config", default=str(HERE / "config.yaml"), help="Path to config.yaml")
    parser.add_argument("--experiment", help="Run only this experiment ID")
    parser.add_argument("--analyze", metavar="RESULTS_DIR", help="Analyze an existing results directory")
    parser.add_argument("--list", action="store_true", help="List all experiment IDs and exit")
    args = parser.parse_args()

    experiments = load_experiments(HERE / "experiments.json")

    if args.list:
        print("Available experiment IDs:")
        for exp in experiments:
            print(f"  {exp['id']:<30} {exp['name']} ({exp.get('paper_result', '?')})")
        return

    if args.analyze:
        results_dir = Path(args.analyze)
        print_comparison_table(experiments, results_dir)
        save_detailed_report(experiments, results_dir, results_dir / "report.md")
        return

    cfg = load_config(Path(args.config))

    # Filter experiments
    if args.experiment:
        experiments = [e for e in experiments if e["id"] == args.experiment]
        if not experiments:
            print(f"No experiment found with id={args.experiment!r}")
            sys.exit(1)
    elif cfg["experiment"].get("run") != "all":
        ids = cfg["experiment"]["run"]
        experiments = [e for e in experiments if e["id"] in ids]

    # Build LLM client
    llm_cfg = cfg["llm"]
    api_key = resolve_api_key(llm_cfg["provider"])
    llm = build_client(
        provider=llm_cfg["provider"],
        model=llm_cfg["model"],
        temperature=float(llm_cfg.get("temperature", 0.7)),
        api_key=api_key,
    )

    # Select personas
    personas = select_personas(
        n=cfg["experiment"].get("n_personas", "all"),
        seed=int(cfg["experiment"].get("seed", 42)),
    )
    print(f"Using {len(personas)} personas, model={llm_cfg['model']}, "
          f"temp={llm_cfg.get('temperature', 0.7)}")

    # Create output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = HERE / cfg["output"]["dir"] / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {out_dir}")

    # Save run metadata
    (out_dir / "config.yaml").write_text(
        (Path(args.config)).read_text()
    )

    # Run experiments
    between_mode = cfg["experiment"].get("between_subject_mode", "within")
    seed = int(cfg["experiment"].get("seed", 42))

    failed = []
    for exp in experiments:
        try:
            rows = run_experiment(
                exp=exp,
                personas=personas,
                llm=llm,
                between_subject_mode=between_mode,
                seed=seed,
                out_dir=out_dir,
            )
            out_path = out_dir / f"{exp['id']}.json"
            out_path.write_text(json.dumps(rows, indent=2))
            print(f"  → saved {len(rows)} rows to {out_path.name}")
        except Exception as exc:
            print(f"  ✗ {exp['id']} FAILED: {exc}", flush=True)
            (out_dir / f"{exp['id']}.error").write_text(str(exc))
            failed.append(exp["id"])

    if failed:
        print(f"\nFailed experiments (re-run with --experiment <id>): {failed}")

    # Print comparison table
    print_comparison_table(experiments, out_dir)
    save_detailed_report(experiments, out_dir, out_dir / "report.md")
    print(f"\nAll results in: {out_dir}")


if __name__ == "__main__":
    main()
