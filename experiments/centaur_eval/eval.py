#!/usr/bin/env python3
"""
eval.py — Evaluate marcelbinz/Llama-3.1-Centaur-70B on the 16 Twin-2K bias studies

Centaur is a foundation model of human cognition fine-tuned on large-scale behavioral data
(Binz et al., 2024). It uses <<...>> tokens to encapsulate human choices — no JSON.
We use constrained logit masking to force a valid answer token (A/B for choice, digit for
scale) and fall back to short free-text generation for open numeric questions.

Personas from Doppelganger's DEFAULT_PERSONAS are included in prompts for individual-level
variation, even though they are out-of-distribution for Centaur's original training format.
The <<X>> context injection is used for two-pass studies (false_consensus, risk_benefit).

Usage:
  python eval.py                        # run all 16 experiments
  python eval.py --experiment framing   # single experiment
  python eval.py --analyze              # re-analyze existing results without model
  python eval.py --list                 # list experiment IDs
  python eval.py --model-path /path/    # local checkpoint or alternate HF ID
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path
from typing import Any

import torch
import yaml

ROOT = Path(__file__).resolve().parents[2]
TWIN2K = ROOT / "experiments" / "twin2k_replication"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(TWIN2K))

from runner import select_personas
from analysis import analyze_experiment, print_comparison_table, save_detailed_report
from llm_client import LLMClient


# ── Prompt & schema builders ──────────────────────────────────────────────────

def _schema(response_type: str, options: list[dict] | None, scale: dict | None) -> dict:
    if response_type == "choice" and options:
        return {
            "type": "object",
            "properties": {"answer": {"type": "string", "enum": [o["id"] for o in options]}},
        }
    if response_type == "scale" and scale:
        return {
            "type": "object",
            "properties": {
                "answer": {"type": "integer", "minimum": scale["min"], "maximum": scale["max"]}
            },
        }
    return {"type": "object", "properties": {"answer": {"type": "number"}}}


def _build_prompt(persona, scenario: str, question: str,
                  options: list[dict] | None, scale: dict | None,
                  response_type: str) -> str:
    """Centaur-style prompt: persona context + scenario + question + options/scale.
    No 'Return JSON' instruction — the client appends 'You press <<' as the response cue."""
    lines = [
        f"PERSONA: {persona.name}",
        persona.description,
        "",
    ]
    if scenario:
        lines += [scenario.strip(), ""]
    lines += [question.strip(), ""]
    if response_type == "choice" and options:
        for opt in options:
            lines.append(f"{opt['id']}: {opt['text']}")
        lines.append("")
    elif response_type == "scale" and scale:
        lines.append(
            f"Scale: {scale['min']} ({scale['min_label']}) "
            f"to {scale['max']} ({scale['max_label']})"
        )
        lines.append("")
    return "\n".join(lines).rstrip()


def _req(key: str, persona, condition: dict) -> dict:
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
        "schema": _schema(
            condition["response_type"],
            condition.get("options"),
            condition.get("scale"),
        ),
    }


def _req_scale(key: str, persona, question: str, scale: dict, scenario: str = "") -> dict:
    return _req(key, persona, {
        "question": question, "scale": scale, "response_type": "scale", "scenario": scenario,
    })


def _req_numeric(key: str, persona, question: str, scenario: str = "") -> dict:
    return _req(key, persona, {"question": question, "response_type": "numeric", "scenario": scenario})


def _extract(raw: dict, key: str) -> Any:
    result = raw.get(key)
    return result.get("answer") if result is not None else None


# ── LocalCentaurClient ────────────────────────────────────────────────────────

class LocalCentaurClient(LLMClient):
    """
    Wraps marcelbinz/Llama-3.1-Centaur-70B for batched GPU inference.

    Centaur uses <<...>> tokens to mark human choices in its training data.
    Every prompt is suffixed with '\n\nYou press <<'. For choice and small-range
    integer questions, a logit mask forces the next token to be a valid answer
    token. Numeric (open-ended) questions fall back to short generate() + regex.

    Loaded in 4-bit (NF4) via bitsandbytes — requires ~38GB VRAM. An A100 80GB
    is strongly recommended; two A40 48GB with device_map="auto" also works.
    """

    _PRESS_SUFFIX = "\n\nYou press <<"

    def __init__(self, model_path: str, temperature: float, batch_size: int = 8):
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

        print(f"Loading model: {model_path}", flush=True)
        bnb_cfg = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
        )
        local = Path(model_path).is_dir()
        self._model = AutoModelForCausalLM.from_pretrained(
            model_path,
            quantization_config=bnb_cfg,
            device_map="auto",
            local_files_only=local,
        )
        self._model.eval()

        self._tokenizer = AutoTokenizer.from_pretrained(
            model_path, local_files_only=local
        )
        self._tokenizer.padding_side = "left"
        if self._tokenizer.pad_token is None:
            self._tokenizer.pad_token = self._tokenizer.eos_token

        self._temperature = temperature
        self._batch_size = batch_size

        # Diagnostic: show how the model tokenizes the << marker
        llt = self._tokenizer.encode("<<", add_special_tokens=False)
        print(f"  '<<' tokenizes to {len(llt)} token(s): {llt}", flush=True)

    # ── Token ID resolution ───────────────────────────────────────────────────

    def _single_tok(self, text: str) -> int | None:
        """Return the single token ID for `text`, or None if it encodes to multiple tokens."""
        ids = self._tokenizer.encode(text, add_special_tokens=False)
        return ids[0] if len(ids) == 1 else None

    def _allowed_ids(self, schema: dict) -> list[int] | None:
        """
        Return allowed next-token IDs for constrained decoding.
        Returns None for open numeric questions (free generation).
        """
        spec = schema.get("properties", {}).get("answer", {})

        enum = spec.get("enum")
        if enum:
            ids: set[int] = set()
            for v in enum:
                s = str(v)
                # Try bare, space-prefixed, lowercase variants — handles tokenizer quirks
                found_for_v: set[int] = set()
                for candidate in [s, " " + s, s.lower(), " " + s.lower()]:
                    tok = self._single_tok(candidate)
                    if tok is not None:
                        found_for_v.add(tok)
                if not found_for_v:
                    # This value has no single-token form (e.g. "vaccinate", "maximize").
                    # Fall back to free generation so the full allowed set is unbiased.
                    return None
                ids.update(found_for_v)
            return list(ids) if ids else None

        if spec.get("type") in ("integer", "number"):
            lo, hi = spec.get("minimum"), spec.get("maximum")
            if lo is not None and hi is not None and (int(hi) - int(lo)) <= 30:
                ids = set()
                for v in range(int(lo), int(hi) + 1):
                    for candidate in [str(v), " " + str(v)]:
                        tok = self._single_tok(candidate)
                        if tok is not None:
                            ids.add(tok)
                return list(ids) if ids else None

        return None  # numeric free generation

    # ── Generation ────────────────────────────────────────────────────────────

    def _render(self, prompt: str) -> str:
        return prompt + self._PRESS_SUFFIX

    def _constrained_batch(self, texts: list[str], allowed_ids: list[int]) -> list[str]:
        """
        Single forward pass + logit masking per batch.
        Returns one answer string per prompt (the most likely allowed token).
        """
        inputs = self._tokenizer(
            texts, return_tensors="pt", padding=True, truncation=False
        )
        input_ids = inputs["input_ids"].to("cuda")
        attn = inputs["attention_mask"].to("cuda")

        with torch.no_grad():
            logits = self._model(input_ids=input_ids, attention_mask=attn).logits

        # Index of the last real token in each sequence (after left-padding)
        last_pos = attn.sum(dim=1) - 1  # [batch]
        last_logits = logits[torch.arange(len(texts)), last_pos]  # [batch, vocab]

        mask = torch.full_like(last_logits, float("-inf"))
        for tid in allowed_ids:
            mask[:, tid] = 0.0
        constrained = last_logits + mask

        if self._temperature > 0:
            probs = torch.softmax(constrained / self._temperature, dim=-1)
            chosen = torch.multinomial(probs, 1).squeeze(1)
        else:
            chosen = constrained.argmax(dim=1)

        return [self._tokenizer.decode([int(tid)]).strip() for tid in chosen.tolist()]

    def _free_batch(self, texts: list[str], max_new_tokens: int = 16) -> list[str]:
        """Short autoregressive generation for open numeric answers."""
        inputs = self._tokenizer(
            texts, return_tensors="pt", padding=True, truncation=False
        ).to("cuda")
        with torch.no_grad():
            out = self._model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=self._temperature if self._temperature > 0 else None,
                do_sample=self._temperature > 0,
                pad_token_id=self._tokenizer.pad_token_id,
            )
        gen = out[:, inputs["input_ids"].shape[1]:]
        return [self._tokenizer.decode(g, skip_special_tokens=True).strip() for g in gen]

    # ── Answer coercion ───────────────────────────────────────────────────────

    @staticmethod
    def _coerce(raw: str, schema: dict) -> dict[str, Any] | None:
        """Map a raw decoded string to a validated answer dict.

        For enum answers: handles single-token (A/B, 1-7) from constrained decoding
        AND multi-token strings (e.g. 'vaccinate', 'maximize') from free generation.
        Centaur output is cleaned up to >> since that ends the <<...>> block.
        """
        spec = schema.get("properties", {}).get("answer", {})
        # Strip Centaur's closing >> and trailing punctuation
        raw = raw.split(">>")[0].strip().rstrip(".,;:!? ")

        enum = spec.get("enum")
        if enum:
            # 1. Exact match
            if raw in enum:
                return {"answer": raw}
            raw_lower = raw.lower()
            # 2. Case-insensitive exact match
            for e in enum:
                if raw_lower == str(e).lower():
                    return {"answer": e}
            # 3. Output starts with an enum value (handles "vaccinate my child" → "vaccinate")
            for e in enum:
                if raw_lower.startswith(str(e).lower()):
                    return {"answer": e}
            # 4. Exactly one enum value appears as a substring of the output
            matches = [e for e in enum if str(e).lower() in raw_lower]
            if len(matches) == 1:
                return {"answer": matches[0]}
            return None

        if spec.get("type") in ("integer", "number"):
            m = re.search(r"-?\d+(?:\.\d+)?", raw.replace(",", "").replace("$", ""))
            if not m:
                return None
            val = float(m.group(0))
            if spec.get("type") == "integer":
                if val != int(val):
                    return None
                val = int(val)
            lo, hi = spec.get("minimum"), spec.get("maximum")
            if (lo is not None and val < lo) or (hi is not None and val > hi):
                return None
            return {"answer": val}

        return {"answer": raw}

    # ── LLMClient interface ───────────────────────────────────────────────────

    def complete(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any] | None:
        rendered = self._render(prompt)
        allowed = self._allowed_ids(schema)
        raw = self._constrained_batch([rendered], allowed)[0] if allowed else self._free_batch([rendered])[0]
        return self._coerce(raw, schema)

    def complete_batch(
        self,
        requests: list[dict[str, Any]],
        *,
        checkpoint_path: str | None = None,
    ) -> dict[str, dict[str, Any] | None]:
        results: dict[str, dict[str, Any] | None] = {}
        if checkpoint_path:
            cp = Path(checkpoint_path)
            if cp.exists():
                results = json.loads(cp.read_text())
                done = sum(1 for v in results.values() if v is not None)
                if done:
                    print(f"  Resuming from checkpoint: {done}/{len(requests)} done", flush=True)

        pending = [r for r in requests if r["key"] not in results]
        rendered = {r["key"]: self._render(r["prompt"]) for r in pending}
        # Sort by prompt length to minimise padding waste within each batch
        pending.sort(key=lambda r: len(rendered[r["key"]]))

        for i in range(0, len(pending), self._batch_size):
            batch = pending[i:i + self._batch_size]
            texts = [rendered[r["key"]] for r in batch]
            # All requests in one complete_batch call share response type
            allowed = self._allowed_ids(batch[0]["schema"])
            try:
                raws = (self._constrained_batch(texts, allowed) if allowed
                        else self._free_batch(texts))
            except Exception as e:
                print(f"  [batch {i // self._batch_size}] failed ({e}); retrying singly",
                      flush=True)
                raws = []
                for t in texts:
                    try:
                        raws.append(self._constrained_batch([t], allowed)[0] if allowed
                                    else self._free_batch([t])[0])
                    except Exception:
                        raws.append("")

            for r, raw in zip(batch, raws):
                results[r["key"]] = self._coerce(raw, r["schema"])

            print(f"  {min(i + len(batch), len(pending))}/{len(pending)} generated", flush=True)
            if checkpoint_path:
                Path(checkpoint_path).write_text(json.dumps(results))

        return results


# ── Experiment runners ────────────────────────────────────────────────────────

LIKERT_5_AGREE = [
    "Strongly disagree", "Somewhat disagree", "Neither agree nor disagree",
    "Somewhat agree", "Strongly agree",
]
LEVEL_7 = ["Very low", "Low", "Somewhat low", "Moderate", "Somewhat high", "High", "Very high"]


def run_between(exp: dict, personas, llm: LLMClient, mode: str, seed: int,
                out_dir: Path) -> list[dict]:
    conditions = exp["conditions"]
    if mode == "between":
        rng = random.Random(seed)
        shuffled = list(personas)
        rng.shuffle(shuffled)
        assignments = [(p, conditions[i % len(conditions)]) for i, p in enumerate(shuffled)]
    else:
        assignments = [(p, c) for p in personas for c in conditions]

    requests = [_req(f"{p.name}::{c['id']}", p, c) for p, c in assignments]
    cp = str(out_dir / f"{exp['id']}.checkpoint.json")
    print(f"  Batching {len(requests)} requests...", flush=True)
    raw = llm.complete_batch(requests, checkpoint_path=cp)

    rows = []
    for (p, c), req in zip(assignments, requests):
        answer = _extract(raw, req["key"])
        rows.append({
            "experiment_id": exp["id"], "persona": p.name,
            "condition_id": c["id"], "condition_name": c["name"],
            "answer": answer, "error": None if answer is not None else "no response",
        })
    return rows


def run_false_consensus(exp: dict, personas, llm: LLMClient, out_dir: Path) -> list[dict]:
    """
    Two-pass with <<X>> prior-answer context.
    Pass 1: ask each persona their own view on each policy (scale 1-5).
    Pass 2: ask public-estimate question, prefixed with prior answers in
            Centaur's '→ You answered <<X>>' format.
    """
    scale_5 = {"min": 1, "max": 5, "min_label": "Strongly disagree", "max_label": "Strongly agree"}
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
        prior_lines = []
        for it in items:
            own = _extract(own_raw, f"{p.name}::{it['id']}::own")
            if isinstance(own, (int, float)) and 1 <= int(own) <= 5:
                label = LIKERT_5_AGREE[int(own) - 1]
                prior_lines.append(
                    f"{it['own_question'].rstrip('.')} → You answered <<{label}>>"
                )

        for it in items:
            prior_block = ""
            if prior_lines:
                prior_block = "YOUR PREVIOUS ANSWERS:\n" + "\n".join(prior_lines) + "\n\n"
            prompt = (
                f"PERSONA: {p.name}\n{p.description}\n\n"
                + prior_block
                + it["public_question"]
            )
            pub_reqs.append({
                "key": f"{p.name}::{it['id']}::public",
                "prompt": prompt,
                "schema": {"type": "object", "properties": {"answer": {"type": "number"}}},
            })

    print(f"  Pass 2/2 — public estimates ({len(pub_reqs)} requests)...", flush=True)
    pub_raw = llm.complete_batch(
        pub_reqs, checkpoint_path=str(out_dir / f"{exp['id']}.public.checkpoint.json"))

    rows = []
    for p in personas:
        for it in items:
            own = _extract(own_raw, f"{p.name}::{it['id']}::own")
            pub = _extract(pub_raw, f"{p.name}::{it['id']}::public")
            rows.append({
                "experiment_id": exp["id"], "persona": p.name, "item_id": it["id"],
                "own_view": own, "public_estimate": pub,
                "error": None if (own is not None and pub is not None) else "no response",
            })
    return rows


def run_risk_benefit(exp: dict, personas, llm: LLMClient, out_dir: Path) -> list[dict]:
    """
    Two-pass with <<X>> prior-answer context.
    Pass 1: benefit ratings (scale 1-7).
    Pass 2: risk ratings, prefixed with '→ You answered <<benefit_label>>'.
    """
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
            benefit = _extract(benefit_raw, f"{p.name}::{it['id']}::benefit")
            prefix = ""
            if isinstance(benefit, (int, float)) and 1 <= int(benefit) <= 7:
                blabel = LEVEL_7[int(benefit) - 1]
                bq = exp["benefit_question"].replace("{label}", it["label"])
                prefix = f"{bq} → You answered <<{blabel}>>\n\n"
            rq = exp["risk_question"].replace("{label}", it["label"])
            prompt = f"PERSONA: {p.name}\n{p.description}\n\n{prefix}{rq}"
            risk_reqs.append({
                "key": f"{p.name}::{it['id']}::risk",
                "prompt": prompt,
                "schema": {"type": "object", "properties": {
                    "answer": {"type": "integer", "minimum": 1, "maximum": 7}
                }},
            })

    print(f"  Pass 2/2 — risk ratings ({len(risk_reqs)} requests)...", flush=True)
    risk_raw = llm.complete_batch(
        risk_reqs, checkpoint_path=str(out_dir / f"{exp['id']}.risk.checkpoint.json"))

    rows = []
    for p in personas:
        for it in items:
            benefit = _extract(benefit_raw, f"{p.name}::{it['id']}::benefit")
            risk = _extract(risk_raw, f"{p.name}::{it['id']}::risk")
            rows.append({
                "experiment_id": exp["id"], "persona": p.name,
                "item_id": it["id"], "item_label": it["label"],
                "risk_rating": risk, "benefit_rating": benefit,
                "error": None if (risk is not None and benefit is not None) else "no response",
            })
    return rows


def run_single_condition(exp: dict, personas, llm: LLMClient, out_dir: Path) -> list[dict]:
    """For probability_matching and dominator_neglect (single condition, within-subject)."""
    cond = exp["conditions"][0]
    requests = [_req(p.name, p, cond) for p in personas]
    cp = str(out_dir / f"{exp['id']}.checkpoint.json")
    print(f"  Batching {len(requests)} requests...", flush=True)
    raw = llm.complete_batch(requests, checkpoint_path=cp)
    rows = []
    for p, req in zip(personas, requests):
        answer = _extract(raw, req["key"])
        rows.append({
            "experiment_id": exp["id"], "persona": p.name,
            "answer": answer, "error": None if answer is not None else "no response",
        })
    return rows


def run_omission_bias(exp: dict, personas, llm: LLMClient, out_dir: Path) -> list[dict]:
    """Within-subject: each persona sees both commission and omission conditions."""
    conditions = exp["conditions"]
    requests = [_req(f"{p.name}::{c['id']}", p, c) for p in personas for c in conditions]
    cp = str(out_dir / f"{exp['id']}.checkpoint.json")
    print(f"  Batching {len(requests)} requests...", flush=True)
    raw = llm.complete_batch(requests, checkpoint_path=cp)
    rows = []
    for p in personas:
        for c in conditions:
            answer = _extract(raw, f"{p.name}::{c['id']}")
            rows.append({
                "experiment_id": exp["id"], "persona": p.name,
                "condition_id": c["id"], "answer": answer,
                "error": None if answer is not None else "no response",
            })
    return rows


def run_centaur_experiment(exp: dict, personas, llm: LLMClient, mode: str, seed: int,
                           out_dir: Path) -> list[dict]:
    analysis_type = exp.get("analysis", {}).get("type", "")
    print(f"\n[{exp['id']}] {exp['name']}", flush=True)

    if analysis_type == "false_consensus_correlation":
        return run_false_consensus(exp, personas, llm, out_dir)
    if analysis_type == "within_correlation":
        return run_risk_benefit(exp, personas, llm, out_dir)
    if exp["id"] == "omission_bias":
        return run_omission_bias(exp, personas, llm, out_dir)
    if analysis_type in ("proportion_matching", "proportion_dominated"):
        return run_single_condition(exp, personas, llm, out_dir)
    return run_between(exp, personas, llm, mode, seed, out_dir)


# ── Analysis-only mode ────────────────────────────────────────────────────────

def run_analyze(all_exps: list[dict], out_dir: Path) -> None:
    print(f"\nAnalyzing existing results in {out_dir}")
    print_comparison_table(all_exps, out_dir)
    save_detailed_report(all_exps, out_dir, out_dir / "report.md")

    # Print a simple count
    found = sum(
        1 for exp in all_exps
        if (out_dir / f"{exp['id']}.json").exists()
        and analyze_experiment(
            exp, json.loads((out_dir / f"{exp['id']}.json").read_text())
        ).get("replicated")
    )
    print(f"\n  Centaur replicated {found}/{len(all_exps)} expected human bias effects")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate Centaur-70B on the 16 Twin-2K bias studies"
    )
    parser.add_argument(
        "--model-path", default=None,
        help="HuggingFace ID or local path (default: from config.yaml)",
    )
    parser.add_argument("--experiment", default=None, help="Run a single experiment by ID")
    parser.add_argument("--list", action="store_true", help="Print experiment IDs and exit")
    parser.add_argument("--analyze", action="store_true",
                        help="Re-analyze existing results without loading the model")
    parser.add_argument("--n-personas", type=int, default=None)
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    cfg_path = Path(__file__).parent / "config.yaml"
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f)

    exp_path = TWIN2K / "experiments.json"
    all_exps = json.loads(exp_path.read_text())

    out_dir = Path(__file__).parent / "results"
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.list:
        for e in all_exps:
            print(e["id"])
        return

    if args.analyze:
        run_analyze(all_exps, out_dir)
        return

    eval_cfg = cfg["eval"]
    model_path = args.model_path or cfg["model"]["id"]
    n_personas = args.n_personas if args.n_personas is not None else eval_cfg["n_personas"]
    temperature = args.temperature if args.temperature is not None else eval_cfg["temperature"]
    seed = args.seed if args.seed is not None else eval_cfg["seed"]
    bsm = eval_cfg["between_subject_mode"]
    batch_size = eval_cfg.get("batch_size", 8)

    if args.experiment:
        all_exps = [e for e in all_exps if e["id"] == args.experiment]
        if not all_exps:
            print(f"Unknown experiment: {args.experiment}")
            sys.exit(1)

    llm = LocalCentaurClient(
        model_path=model_path,
        temperature=temperature,
        batch_size=batch_size,
    )

    personas = select_personas(n_personas, seed)
    print(f"\nModel:       {model_path}")
    print(f"Personas:    {len(personas)}  |  mode: {bsm}  |  seed: {seed}")
    print(f"Temperature: {temperature}  |  batch_size: {batch_size}")
    print(f"Experiments: {len(all_exps)}\n")

    for exp in all_exps:
        rows = run_centaur_experiment(exp, personas, llm, bsm, seed, out_dir)
        (out_dir / f"{exp['id']}.json").write_text(json.dumps(rows, indent=2))

    print(f"\nResults saved to {out_dir}")
    run_analyze(all_exps, out_dir)


if __name__ == "__main__":
    main()
