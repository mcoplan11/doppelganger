#!/usr/bin/env python3
"""
3_eval.py — Run the 16 Twin-2K bias experiments against a Qwen model

Works for both the base model and the fine-tuned checkpoint.

Usage:
  # Base model (before fine-tuning)
  python 3_eval.py --model-path Qwen/Qwen2.5-7B-Instruct --out-label base

  # Fine-tuned model (after training)
  python 3_eval.py --out-label finetuned

  # Side-by-side comparison (after both have been run)
  python 3_eval.py --compare

  # Single experiment
  python 3_eval.py --experiment framing --out-label base
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import torch
import yaml

ROOT = Path(__file__).resolve().parents[2]
TWIN2K = ROOT / "experiments" / "twin2k_replication"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(TWIN2K))

from runner import run_experiment, select_personas
from analysis import analyze_experiment, print_comparison_table
from llm_client import LLMClient


# ── Local model client ────────────────────────────────────────────────────────

class LocalQwenClient(LLMClient):
    """
    Wraps a Qwen model (base or LoRA fine-tuned) for inference.
    Accepts any model_path recognised by FastLanguageModel.from_pretrained:
      - HuggingFace ID  →  loads base model  (e.g. "Qwen/Qwen2.5-7B-Instruct")
      - local directory →  loads fine-tuned checkpoint
    """

    def __init__(self, model_path: str, max_seq_length: int, temperature: float):
        from unsloth import FastLanguageModel

        print(f"Loading model: {model_path}")
        self._model, self._tokenizer = FastLanguageModel.from_pretrained(
            model_name=model_path,
            max_seq_length=max_seq_length,
            load_in_4bit=True,
        )
        FastLanguageModel.for_inference(self._model)
        self._temperature = temperature
        self._max_new_tokens = 64

    def complete(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        schema_hint = json.dumps(schema, indent=2)
        full_prompt = (
            f"{prompt}\n\nReturn ONLY valid JSON matching this schema:\n{schema_hint}"
        )
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": full_prompt},
        ]
        text = self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self._tokenizer(text, return_tensors="pt").to("cuda")

        with torch.no_grad():
            outputs = self._model.generate(
                **inputs,
                max_new_tokens=self._max_new_tokens,
                temperature=self._temperature if self._temperature > 0 else None,
                do_sample=self._temperature > 0,
            )

        generated = outputs[0][inputs["input_ids"].shape[1]:]
        response = self._tokenizer.decode(generated, skip_special_tokens=True).strip()

        if response.startswith("```"):
            response = response.split("```")[1]
            if response.startswith("json"):
                response = response[4:]
            response = response.strip()

        return json.loads(response)


# ── Comparison table ──────────────────────────────────────────────────────────

def print_side_by_side(all_exps: list[dict], results_dir: Path) -> None:
    base_dir = results_dir / "base"
    ft_dir = results_dir / "finetuned"
    has_base = base_dir.exists()
    has_ft = ft_dir.exists()

    if not has_base and not has_ft:
        print("No results found in results/base/ or results/finetuned/")
        return

    print("\n" + "=" * 80)
    print("COMPARISON: BASE QWEN  vs  FINE-TUNED QWEN")
    print("=" * 80)

    if has_base:
        print(f"\n--- Base model ({base_dir}) ---")
        print_comparison_table(all_exps, base_dir)

    if has_ft:
        print(f"\n--- Fine-tuned model ({ft_dir}) ---")
        print_comparison_table(all_exps, ft_dir)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model-path", default=None,
        help="HuggingFace ID or local checkpoint path. "
             "Defaults to checkpoints/final (fine-tuned model).",
    )
    parser.add_argument(
        "--out-label", default="finetuned",
        help="Subdirectory under results/ for this run's output. "
             "Use 'base' for the baseline run, 'finetuned' after training.",
    )
    parser.add_argument("--n-personas", type=int, default=None,
                        help="Overrides config eval.n_personas")
    parser.add_argument("--experiment", default=None,
                        help="Run a single experiment by ID (e.g. framing, linda)")
    parser.add_argument("--temperature", type=float, default=None,
                        help="Overrides config eval.temperature")
    parser.add_argument("--seed", type=int, default=None,
                        help="Overrides config eval.seed")
    parser.add_argument("--compare", action="store_true",
                        help="Print base vs fine-tuned comparison table and exit")
    args = parser.parse_args()

    cfg_path = Path(__file__).parent / "config.yaml"
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f)

    exp_path = TWIN2K / "experiments.json"
    with open(exp_path) as f:
        all_exps = json.load(f)

    results_dir = Path(__file__).parent / "results"

    if args.compare:
        print_side_by_side(all_exps, results_dir)
        return

    eval_cfg = cfg["eval"]
    n_personas   = args.n_personas   or eval_cfg["n_personas"]
    temperature  = args.temperature  or eval_cfg["temperature"]
    seed         = args.seed         or eval_cfg["seed"]
    bsm          = eval_cfg["between_subject_mode"]

    # Default model path: fine-tuned checkpoint
    if args.model_path:
        model_path = args.model_path
    else:
        model_path = str(Path(__file__).parent / "checkpoints" / "final")

    if args.experiment:
        all_exps = [e for e in all_exps if e["id"] == args.experiment]
        if not all_exps:
            print(f"Unknown experiment: {args.experiment}")
            sys.exit(1)

    llm = LocalQwenClient(
        model_path=model_path,
        max_seq_length=cfg["model"]["max_seq_length"],
        temperature=temperature,
    )

    personas = select_personas(n_personas, seed)
    print(f"Model:      {model_path}")
    print(f"Out label:  {args.out_label}")
    print(f"Personas:   {len(personas)}  |  mode: {bsm}  |  seed: {seed}")
    print(f"Experiments: {len(all_exps)}\n")

    out_dir = results_dir / args.out_label
    out_dir.mkdir(parents=True, exist_ok=True)

    for exp in all_exps:
        rows = run_experiment(
            exp=exp,
            personas=personas,
            llm=llm,
            between_subject_mode=bsm,
            seed=seed,
            out_dir=out_dir,
        )
        result_path = out_dir / f"{exp['id']}.json"
        result_path.write_text(json.dumps(rows, indent=2))

    print(f"\nResults saved to {out_dir}")
    print("\n" + "=" * 70)
    print(f"{'BASE' if args.out_label == 'base' else 'FINE-TUNED'} MODEL — 16 BIAS EXPERIMENTS")
    print("=" * 70)
    print_comparison_table(all_exps, out_dir)

    # If the other run also exists, print the side-by-side automatically
    other_label = "finetuned" if args.out_label == "base" else "base"
    if (results_dir / other_label).exists():
        print_side_by_side(all_exps, results_dir)


if __name__ == "__main__":
    main()
