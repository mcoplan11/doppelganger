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
import os
import re
import sys
from pathlib import Path
from typing import Any

# Redirect HuggingFace downloads to /workspace if present, BEFORE importing torch
# or any HF library (env vars are read at import time). RunPod container disks are
# tiny (~20GB); the 30B base model (~60GB) overflows them → "Disk quota exceeded".
# 2_train.py does the same; eval must match or base_30b fails first. (no-op locally)
if Path("/workspace").is_dir():
    _hf_cache = "/workspace/hf_cache"
    os.environ.setdefault("HF_HOME", _hf_cache)
    os.environ.setdefault("HF_HUB_CACHE", f"{_hf_cache}/hub")
    os.environ.setdefault("TRANSFORMERS_CACHE", f"{_hf_cache}/hub")
    # The xet transfer protocol caches chunks on the tiny container disk
    # regardless of HF_HOME → "Disk quota exceeded"; disable it so downloads use
    # the normal HTTPS path into HF_HUB_CACHE above.
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    os.environ.setdefault("HF_XET_CACHE", f"{_hf_cache}/xet")

import torch
import yaml

ROOT = Path(__file__).resolve().parents[2]
TWIN2K = ROOT / "experiments" / "twin2k_replication"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(TWIN2K))

from runner import run_experiment, _req_scale, _req_numeric, _extract
from analysis import analyze_experiment, print_comparison_table
from llm_client import LLMClient


# ── Prolific eval-persona roster ──────────────────────────────────────────────

from personas import DEFAULT_PERSONAS as _PROLIFIC_PERSONAS

def load_prolific_eval_personas(n: int, seed: int) -> list[Persona]:
    """Return up to n personas from the hand-crafted Prolific-worker roster.

    Training uses all 2,058 Twin-2K participants (representative US), but
    inference uses this Prolific-skewed roster to match the product's real
    respondent population (§3.3 train-broad/query-narrow).
    """
    import random
    rng = random.Random(seed)
    pool = list(_PROLIFIC_PERSONAS)
    if len(pool) <= n:
        return pool
    return rng.sample(pool, n)


# ── Local model client ────────────────────────────────────────────────────────

class LocalQwenClient(LLMClient):
    """
    Wraps a Qwen model (base or LoRA fine-tuned) for inference.
    Accepts any model_path recognised by FastLanguageModel.from_pretrained:
      - HuggingFace ID  →  loads base model  (e.g. "Qwen/Qwen2.5-7B-Instruct")
      - local directory →  loads fine-tuned checkpoint

    The prompt is sent as a single user message with no system prompt and no
    appended schema block — matching the training prompt format in 1_prepare_data.py
    so the fine-tuned LoRA sees the distribution it was trained on. The runner's
    prompt already ends in `Return JSON: {"answer": ...}`.
    """

    def __init__(self, model_path: str, max_seq_length: int, temperature: float,
                 batch_size: int = 32, seed: int = 42):
        from transformers import AutoModelForCausalLM, AutoTokenizer

        # Seed torch so sampled generation (temperature > 0) is reproducible
        # run-to-run — otherwise the config `seed` only fixes persona sampling and
        # a borderline gate result (e.g. myside) would jitter between runs.
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)

        print(f"Loading model: {model_path}")
        dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16

        def _load_base(name: str) -> "AutoModelForCausalLM":
            local = Path(name).is_dir()
            return AutoModelForCausalLM.from_pretrained(
                name, torch_dtype=dtype, device_map="auto",
                trust_remote_code=True, local_files_only=local,
            )

        def _resolve_hf_cache(model_id: str) -> str:
            hf_home = os.environ.get("HF_HOME", str(Path.home() / ".cache" / "huggingface"))
            slug = model_id.replace("/", "--")
            snaps = Path(hf_home) / "hub" / f"models--{slug}" / "snapshots"
            if snaps.exists():
                candidates = sorted(snaps.iterdir())
                if candidates:
                    return str(candidates[-1])
            return model_id

        adapter_cfg_path = Path(model_path) / "adapter_config.json"
        # A LoRA checkpoint was SFT'd on plain ChatML (see 2_train.py:
        # get_chat_template(..., "chatml")) with the answer JSON emitted directly
        # after the assistant tag — NO thinking block. The base reference is a
        # raw HF model. _render branches on this so each model sees the exact
        # surface it expects; otherwise Qwen3's native template injects a <think>
        # turn that starves the answer under a small token budget (collapse).
        self._is_finetuned = Path(model_path).is_dir() and adapter_cfg_path.exists()
        if self._is_finetuned:
            # LoRA adapter checkpoint. Training applied LoRA to the FUSED MoE expert
            # tensors (mlp.experts.gate_up_proj / down_proj) via Unsloth — those are
            # custom fused params, NOT nn.Linear, so vanilla PeftModel.from_pretrained
            # cannot inject the adapter and dies walking the Qwen3-MoE block
            # ("...Qwen3MoeRMSNorm... is not supported"). Load through Unsloth instead,
            # mirroring 2_train.py: it resolves the base from adapter_config, applies
            # the MoE-expert adapter, and returns the matching tokenizer. Do NOT merge
            # — merging fused MoE experts is unsupported and unneeded for inference.
            # See GROUNDED_PERSONAS_PLAN §2.3.
            from unsloth import FastLanguageModel
            print(f"  Loading FT checkpoint via Unsloth: {model_path}")
            self._model, self._tokenizer = FastLanguageModel.from_pretrained(
                model_name=model_path,
                max_seq_length=max_seq_length,
                dtype=dtype,
                load_in_4bit=False,
            )
            FastLanguageModel.for_inference(self._model)
            tokenizer_src = None  # tokenizer already returned by Unsloth
        else:
            self._model = _load_base(model_path)
            tokenizer_src = model_path

        self._model.eval()
        if tokenizer_src is not None:
            tok_local = Path(tokenizer_src).is_dir()
            self._tokenizer = AutoTokenizer.from_pretrained(
                tokenizer_src, trust_remote_code=True, local_files_only=tok_local)
        # Left-padding is required for correct decoder-only batch generation.
        self._tokenizer.padding_side = "left"
        if self._tokenizer.pad_token is None:
            self._tokenizer.pad_token = self._tokenizer.eos_token
        self._temperature = temperature
        # Answers are a tiny JSON object; 64 was fine with thinking OFF, but give
        # headroom so a stray short reasoning preamble can't truncate the answer.
        self._max_new_tokens = 128
        self._batch_size = batch_size

    def _render(self, prompt: str) -> str:
        """Render a single user turn, reasoning OFF (§3.5), matching training.

        Fine-tuned checkpoints were SFT'd on plain ChatML with the answer emitted
        directly after the assistant tag, so we reproduce that surface byte-for-byte
        — using Qwen3's native template here would inject a <think> turn the LoRA
        never saw and starve the answer under the token budget (answer-format
        collapse, misread as "grounding didn't help"; see GROUNDED_PERSONAS_PLAN §3.5).
        The base reference uses its native template with thinking explicitly OFF.
        """
        if self._is_finetuned:
            return (
                f"<|im_start|>user\n{prompt}<|im_end|>\n"
                f"<|im_start|>assistant\n"
            )
        messages = [{"role": "user", "content": prompt}]
        try:
            # Qwen3 honors enable_thinking; harmless kwarg is rejected by older
            # templates, so fall back to a manual ChatML render on TypeError.
            return self._tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True,
                enable_thinking=False,
            )
        except TypeError:
            return (
                f"<|im_start|>user\n{prompt}<|im_end|>\n"
                f"<|im_start|>assistant\n"
            )

    @staticmethod
    def _coerce(parsed: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any] | None:
        """Validate (and where safe, repair) a parsed answer against the request schema.

        The fine-tuned model is trained to answer MC questions with option letters,
        while the eval's option ids are semantic strings ('michigan', 'yes', …).
        Without this guard a stray letter is silently counted as the *non-risky*
        option by analysis.py instead of surfacing as an error. Letters map to the
        enum by position (training lists options in the same order); anything
        unparseable or out of range becomes None and is counted as "no response".
        """
        if not isinstance(parsed, dict) or "answer" not in parsed:
            return None
        ans = parsed["answer"]
        spec = schema.get("properties", {}).get("answer", {})

        enum = spec.get("enum")
        if enum:
            if ans in enum:
                return parsed
            s = str(ans).strip()
            for e in enum:
                if s.lower() == str(e).lower():
                    return {"answer": e}
            if len(s) == 1 and s.isalpha():
                idx = ord(s.upper()) - ord("A")
                if 0 <= idx < len(enum):
                    return {"answer": enum[idx]}
            return None

        if spec.get("type") in ("integer", "number"):
            try:
                val = float(ans)
            except (TypeError, ValueError):
                match = re.search(r"-?\d+(?:\.\d+)?", str(ans).replace(",", "").replace("$", ""))
                if not match:
                    return None
                val = float(match.group(0))
            if spec.get("type") == "integer":
                if val != int(val):
                    return None
                val = int(val)
            lo, hi = spec.get("minimum"), spec.get("maximum")
            if (lo is not None and val < lo) or (hi is not None and val > hi):
                return None
            return {"answer": val}

        return parsed

    @staticmethod
    def _parse(response: str) -> dict[str, Any]:
        response = response.strip()
        if response.startswith("```"):
            response = response.split("```")[1]
            if response.startswith("json"):
                response = response[4:]
            response = response.strip()
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # Salvage the first {...} object the model emitted.
            match = re.search(r"\{.*?\}", response, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            raise

    def _generate(self, texts: list[str]) -> list[str]:
        inputs = self._tokenizer(
            texts, return_tensors="pt", padding=True, truncation=False
        ).to("cuda")
        with torch.no_grad():
            outputs = self._model.generate(
                **inputs,
                max_new_tokens=self._max_new_tokens,
                temperature=self._temperature if self._temperature > 0 else None,
                do_sample=self._temperature > 0,
                pad_token_id=self._tokenizer.pad_token_id,
            )
        gen = outputs[:, inputs["input_ids"].shape[1]:]
        return [self._tokenizer.decode(g, skip_special_tokens=True) for g in gen]

    def complete(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        return self._coerce(self._parse(self._generate([self._render(prompt)])[0]), schema)

    def complete_batch(
        self,
        requests: list[dict[str, Any]],
        *,
        checkpoint_path: str | None = None,
    ) -> dict[str, dict[str, Any] | None]:
        """True GPU-batched generation. Overrides the base class's sequential loop.

        Requests are sorted by prompt length so each batch pads to a similar size,
        then generated in groups of `batch_size`. Results are checkpointed per batch
        so a crashed run resumes without re-doing completed work.
        """
        results: dict[str, dict[str, Any] | None] = {}
        if checkpoint_path:
            cp = Path(checkpoint_path)
            if cp.exists():
                results = json.loads(cp.read_text())
                done = sum(1 for v in results.values() if v is not None)
                if done:
                    print(f"  Resuming from checkpoint: {done}/{len(requests)} done", flush=True)

        pending = [r for r in requests if r["key"] not in results]
        # Sort by rendered length to minimise padding within each batch.
        rendered = {r["key"]: self._render(r["prompt"]) for r in pending}
        pending.sort(key=lambda r: len(rendered[r["key"]]))

        for i in range(0, len(pending), self._batch_size):
            batch = pending[i:i + self._batch_size]
            texts = [rendered[r["key"]] for r in batch]
            try:
                outputs = self._generate(texts)
            except Exception as e:  # OOM or generation failure — fall back per item
                print(f"  [batch {i // self._batch_size}] failed ({e}); retrying singly", flush=True)
                outputs = []
                for t in texts:
                    try:
                        outputs.append(self._generate([t])[0])
                    except Exception:
                        outputs.append("")
            for r, out in zip(batch, outputs):
                try:
                    results[r["key"]] = self._coerce(self._parse(out), r["schema"])
                except Exception:
                    results[r["key"]] = None
            print(f"  {min(i + len(batch), len(pending))}/{len(pending)} generated", flush=True)
            if checkpoint_path:
                Path(checkpoint_path).write_text(json.dumps(results))

        return results


# ── Context-matched two-pass runners ─────────────────────────────────────────
#
# Training (1_prepare_data.py) injects prior answers as "YOUR ANSWERS SO FAR"
# context: false_consensus public estimates see the persona's own views, and
# risk ratings see the same item's benefit rating. The shared runner issues all
# requests independently, so the learned conditional would never activate at
# eval. These two-pass variants ask the first-stage questions, then feed each
# persona's actual answers back as context — matching both the training format
# and what human participants saw on screen.

LIKERT_5_AGREE = ["Strongly disagree", "Somewhat disagree",
                  "Neither agree nor disagree", "Somewhat agree", "Strongly agree"]
LEVEL_7 = ["Very low", "Low", "Somewhat low", "Moderate",
           "Somewhat high", "High", "Very high"]


def _with_context(req: dict, prior_qa: list[tuple[str, str]]) -> dict:
    """Insert a training-style prior-answer block before the QUESTION: header."""
    lines = ["YOUR ANSWERS SO FAR (stay consistent with these):"]
    for q_text, a_text in prior_qa:
        lines.append(f"  {q_text}")
        lines.append(f"    → {a_text}")
    block = "\n".join(lines) + "\n\n"
    req = dict(req)
    req["prompt"] = req["prompt"].replace("QUESTION:", block + "QUESTION:", 1)
    return req


def run_false_consensus_two_pass(exp, personas, llm, out_dir: Path) -> list[dict]:
    scale_5 = {"min": 1, "max": 5,
               "min_label": "Strongly disagree", "max_label": "Strongly agree"}
    items = exp["items"]

    own_reqs = [
        _req_scale(f"{p.name}::{it['id']}::own", p, it["own_question"], scale_5)
        for p in personas for it in items
    ]
    print(f"  Pass 1/2 — own views ({len(own_reqs)} requests)...", flush=True)
    own_raw = llm.complete_batch(
        own_reqs, checkpoint_path=str(out_dir / f"{exp['id']}.own.checkpoint.json"))

    pub_reqs = []
    for p in personas:
        prior = []
        for it in items:
            own = _extract(own_raw, f"{p.name}::{it['id']}::own")
            if isinstance(own, (int, float)) and 1 <= int(own) <= 5:
                prior.append((it["own_question"], LIKERT_5_AGREE[int(own) - 1]))
        for it in items:
            req = _req_numeric(f"{p.name}::{it['id']}::public", p, it["public_question"])
            pub_reqs.append(_with_context(req, prior) if prior else req)
    print(f"  Pass 2/2 — public estimates ({len(pub_reqs)} requests)...", flush=True)
    pub_raw = llm.complete_batch(
        pub_reqs, checkpoint_path=str(out_dir / f"{exp['id']}.public.checkpoint.json"))

    rows = []
    for p in personas:
        for it in items:
            own = _extract(own_raw, f"{p.name}::{it['id']}::own")
            pub = _extract(pub_raw, f"{p.name}::{it['id']}::public")
            rows.append({
                "experiment_id": exp["id"],
                "persona": p.name,
                "item_id": it["id"],
                "own_view": own,
                "public_estimate": pub,
                "error": None if (own is not None and pub is not None) else "no response",
            })
    return rows


def run_risk_benefit_two_pass(exp, personas, llm, out_dir: Path) -> list[dict]:
    scale_7 = {"min": 1, "max": 7, "min_label": "Very low", "max_label": "Very high"}
    items = exp["items"]

    benefit_reqs = [
        _req_scale(f"{p.name}::{it['id']}::benefit", p,
                   exp["benefit_question"].replace("{label}", it["label"]), scale_7)
        for p in personas for it in items
    ]
    print(f"  Pass 1/2 — benefit ratings ({len(benefit_reqs)} requests)...", flush=True)
    benefit_raw = llm.complete_batch(
        benefit_reqs, checkpoint_path=str(out_dir / f"{exp['id']}.benefit.checkpoint.json"))

    risk_reqs = []
    for p in personas:
        for it in items:
            req = _req_scale(f"{p.name}::{it['id']}::risk", p,
                             exp["risk_question"].replace("{label}", it["label"]), scale_7)
            benefit = _extract(benefit_raw, f"{p.name}::{it['id']}::benefit")
            if isinstance(benefit, (int, float)) and 1 <= int(benefit) <= 7:
                benefit_q = exp["benefit_question"].replace("{label}", it["label"])
                req = _with_context(req, [(benefit_q, LEVEL_7[int(benefit) - 1])])
            risk_reqs.append(req)
    print(f"  Pass 2/2 — risk ratings ({len(risk_reqs)} requests)...", flush=True)
    risk_raw = llm.complete_batch(
        risk_reqs, checkpoint_path=str(out_dir / f"{exp['id']}.risk.checkpoint.json"))

    rows = []
    for p in personas:
        for it in items:
            benefit = _extract(benefit_raw, f"{p.name}::{it['id']}::benefit")
            risk = _extract(risk_raw, f"{p.name}::{it['id']}::risk")
            rows.append({
                "experiment_id": exp["id"],
                "persona": p.name,
                "item_id": it["id"],
                "item_label": it["label"],
                "risk_rating": risk,
                "benefit_rating": benefit,
                "error": None if (risk is not None and benefit is not None) else "no response",
            })
    return rows


# ── Comparison table ──────────────────────────────────────────────────────────

def print_side_by_side(all_exps: list[dict], results_dir: Path,
                       labels: list[str] | None = None) -> None:
    """Print one comparison table per result label.

    `labels` defaults to ["base", "finetuned"] for backward compatibility, but the
    Phase-1 run matrix (GROUNDED_PERSONAS_PLAN §Stage 3) uses ["base_30b",
    "run0_fictional", "runA_grounded"] — pass those via --compare-labels so the
    grounding comparison (Run A vs Run 0) is actually rendered.
    """
    labels = labels or ["base", "finetuned"]
    present = [(lbl, results_dir / lbl) for lbl in labels if (results_dir / lbl).exists()]

    if not present:
        searched = ", ".join(f"results/{lbl}/" for lbl in labels)
        print(f"No results found in {searched}")
        return

    print("\n" + "=" * 80)
    print("COMPARISON: " + "  vs  ".join(lbl for lbl, _ in present))
    print("=" * 80)

    for lbl, d in present:
        print(f"\n--- {lbl} ({d}) ---")
        print_comparison_table(all_exps, d)


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
                        help="Print a side-by-side comparison table and exit")
    parser.add_argument("--compare-labels", nargs="+", default=None,
                        help="Result labels to compare (default: base finetuned). "
                             "For the Phase-1 matrix use: base_30b run0_fictional runA_grounded")
    args = parser.parse_args()

    cfg_path = Path(__file__).parent / "config.yaml"
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f)

    exp_path = TWIN2K / "experiments.json"
    with open(exp_path) as f:
        all_exps = json.load(f)

    results_dir = Path(__file__).parent / "results"

    if args.compare:
        print_side_by_side(all_exps, results_dir, labels=args.compare_labels)
        return

    eval_cfg = cfg["eval"]
    # Use `is not None` so explicit zeros (e.g. --temperature 0 for greedy decoding,
    # --seed 0) aren't silently overridden by the config defaults.
    n_personas   = args.n_personas  if args.n_personas  is not None else eval_cfg["n_personas"]
    temperature  = args.temperature if args.temperature is not None else eval_cfg["temperature"]
    seed         = args.seed        if args.seed        is not None else eval_cfg["seed"]
    bsm          = eval_cfg["between_subject_mode"]

    # Default model path: fine-tuned checkpoint.
    # On RunPod, checkpoints are saved to /workspace/checkpoints (large volume).
    if args.model_path:
        model_path = args.model_path
    else:
        workspace_ckpt = Path("/workspace/checkpoints/final")
        local_ckpt = Path(__file__).parent / "checkpoints" / "final"
        model_path = str(workspace_ckpt if workspace_ckpt.is_dir() else local_ckpt)

    if args.experiment:
        all_exps = [e for e in all_exps if e["id"] == args.experiment]
        if not all_exps:
            print(f"Unknown experiment: {args.experiment}")
            sys.exit(1)

    llm = LocalQwenClient(
        model_path=model_path,
        max_seq_length=cfg["model"]["max_seq_length"],
        temperature=temperature,
        batch_size=eval_cfg.get("batch_size", 32),
        seed=seed,
    )

    personas = load_prolific_eval_personas(n_personas, seed)
    print(f"  [prolific] Using {len(personas)} Prolific-worker personas from DEFAULT_PERSONAS")
    print(f"Model:      {model_path}")
    print(f"Out label:  {args.out_label}")
    print(f"Personas:   {len(personas)}  |  mode: {bsm}  |  seed: {seed}")
    print(f"Experiments: {len(all_exps)}\n")

    out_dir = results_dir / args.out_label
    out_dir.mkdir(parents=True, exist_ok=True)

    for exp in all_exps:
        analysis_type = exp.get("analysis", {}).get("type", "")
        if analysis_type == "false_consensus_correlation":
            print(f"\n[{exp['id']}] {exp['name']} (two-pass, context-matched)", flush=True)
            rows = run_false_consensus_two_pass(exp, personas, llm, out_dir)
        elif analysis_type == "within_correlation":
            print(f"\n[{exp['id']}] {exp['name']} (two-pass, context-matched)", flush=True)
            rows = run_risk_benefit_two_pass(exp, personas, llm, out_dir)
        else:
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
    print(f"{'BASE' if args.out_label == 'base' else 'FINE-TUNED'} MODEL — {len(all_exps)} BIAS EXPERIMENTS")
    print("=" * 70)
    print_comparison_table(all_exps, out_dir)

    # If the other run also exists, print the side-by-side automatically
    other_label = "finetuned" if args.out_label == "base" else "base"
    if (results_dir / other_label).exists():
        print_side_by_side(all_exps, results_dir)


if __name__ == "__main__":
    main()
