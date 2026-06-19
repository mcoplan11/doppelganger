#!/usr/bin/env python3
"""
prompt_parity_check.py — is each study TRAINED in-sample or only TESTED by transfer?

A GPU-free interpretation aid for the grounded-persona pipeline. The fine-tuned
model is SFT'd on prompts built by `1_prepare_data.py`'s per-study builders, but
evaluated on prompts built independently by `twin2k_replication/runner.py`. This
is NOT a problem in itself: the eval already paraphrases the scenario for every
study (e.g. framing trains on "unusual disease", evals on "unusual *Asian*
disease"), which is the point — it tests whether the model learned the construct
rather than memorising one question's answers.

What this tool flags is the narrower case where the *answer space itself* differs
— different response type (int vs enum), different number of options, or a
different elicitation entirely. When that happens for a study, the training data
for it teaches a *different task* than the eval grades, so the SFT contributes ~no
IN-SAMPLE signal toward that study's eval — it becomes a TRANSFER-ONLY test. That
is an interpretation fact (don't expect grounding to move it in-sample, and don't
pick it as the in-sample gate, §8), NOT a mechanical break: at eval the model is
conditioned on the *eval* prompt, so it still produces parseable output as long as
it follows instructions. (Output collapse is a separate SFT-overfitting risk,
monitored by the eval's per-study no-response rate and the degenerate-label flag
in 1_prepare_data.py — and is, if anything, likelier on the matched studies.)

What it does, per study:
  • collect the SET of answer SPACES (`Return JSON:` lines → type+range/cardinality,
    gloss text ignored) that TRAINING emits, from the real built examples;
  • collect the SET that EVAL emits, by replaying runner.py's request builders;
  • classify: ✓ in-sample-compatible / △ order-dependent enum / ↔ transfer-only.

Exit status is always 0 (informational); read the per-study verdicts.

Usage:
    python prompt_parity_check.py
    python prompt_parity_check.py --show-bodies   # also print full prompt tails
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TWIN2K = ROOT / "experiments" / "twin2k_replication"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(TWIN2K))

# Scale constants copied verbatim from runner.run_false_consensus /
# run_risk_benefit so the replayed eval prompts match production exactly.
SCALE_5 = {"min": 1, "max": 5, "min_label": "Strongly disagree", "max_label": "Strongly agree"}
SCALE_7 = {"min": 1, "max": 7, "min_label": "Very low", "max_label": "Very high"}

_RETURN_RE = re.compile(r"^Return JSON:.*$", re.MULTILINE)


def _answer_space(line: str):
    """Normalise a `Return JSON:` line to its ANSWER SPACE, ignoring gloss text.

    The eval parser (3_eval.py:_coerce) accepts any integer in range and maps a
    letter to the enum by position, so what matters for parity is the *space*
    (type + range/cardinality), not the human-readable labels. Returns a tuple:
      ("int", lo, hi)   integer scale         — compatible iff same lo/hi
      ("num",)          free number           — compatible with any other num
      ("enum", n)       categorical, n options — letter↔semantic is bridged by
                        _coerce ONLY when n matches AND option order aligns
      ("raw", text)     unparsed (treat as exact-match required)
    """
    m = re.search(r"one of \[([^\]]*)\]", line)
    if m:
        return ("enum", tuple(re.findall(r"'([^']*)'", m.group(1))))
    m = re.search(r"integer\s+(?:from\s+)?(\d+)\s*(?:to|[–\-])\s*(\d+)", line)
    if m:
        return ("int", int(m.group(1)), int(m.group(2)))
    m = re.search(r"number\s+(\d+)\s*[–\-]\s*(\d+)", line)
    if m:
        return ("num",)  # range gloss differs harmlessly; parser takes any number
    if "number" in line:
        return ("num",)
    return ("raw", line.strip())


def _load_prep_module():
    """Import 1_prepare_data.py despite its leading-digit (non-identifier) name."""
    spec = importlib.util.spec_from_file_location("prep", HERE / "1_prepare_data.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _contract_lines(prompt: str) -> set[str]:
    """The set of `Return JSON:` answer-contract lines in a prompt (whitespace-normalised)."""
    return {m.strip() for m in _RETURN_RE.findall(prompt)}


def _eval_requests_for(exp: dict, persona) -> list[dict]:
    """Replay runner.run_experiment's dispatch to build this study's eval prompts.

    Mirrors runner.py exactly (false_consensus / risk_benefit use bespoke
    request builders; everything else is one _req per condition).
    """
    from runner import _req, _req_scale, _req_numeric

    atype = exp.get("analysis", {}).get("type", "")
    reqs: list[dict] = []
    if atype == "false_consensus_correlation":
        for item in exp.get("items", []):
            reqs.append(_req_scale("own", persona, item["own_question"], SCALE_5))
            reqs.append(_req_numeric("pub", persona, item["public_question"]))
    elif atype == "within_correlation":
        for item in exp.get("items", []):
            risk_q = exp["risk_question"].replace("{label}", item["label"])
            benefit_q = exp["benefit_question"].replace("{label}", item["label"])
            reqs.append(_req_scale("risk", persona, risk_q, SCALE_7))
            reqs.append(_req_scale("benefit", persona, benefit_q, SCALE_7))
    else:
        for cond in exp.get("conditions", []):
            reqs.append(_req(cond.get("id", "c"), persona, cond))
    return reqs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show-bodies", action="store_true",
                    help="Also print the full prompt tail (question + contract) per side")
    args = ap.parse_args()

    prep = _load_prep_module()
    from personas import DEFAULT_PERSONAS

    print("Loading catalog + responses + grounded persona map...")
    catalog = prep.load_question_catalog()
    df = prep.load_response_labels()
    out = HERE / "data"
    if not (out / "pid_to_persona.json").exists():
        raise SystemExit("data/pid_to_persona.json not found — run personas_from_twin2k.py first.")
    pid_to_persona = prep.load_grounded_pid_to_persona(out)

    print("Building TRAIN examples (reusing training builders)...")
    train_ex, _ = prep.build_all_examples(
        catalog, df, pid_to_persona, max_examples=None, val_fraction=0.0, seed=42,
    )
    train_contracts: dict[str, set[str]] = defaultdict(set)
    train_sample: dict[str, str] = {}
    for ex in train_ex:
        study = (ex.get("_meta") or {}).get("study")
        if not study:
            continue
        content = ex["messages"][0]["content"]
        train_contracts[study] |= _contract_lines(content)
        train_sample.setdefault(study, content)

    print("Building EVAL prompts (replaying runner.py)...")
    with open(TWIN2K / "experiments.json") as f:
        experiments = json.load(f)
    eval_persona = DEFAULT_PERSONAS[0]
    eval_contracts: dict[str, set[str]] = defaultdict(set)
    eval_sample: dict[str, str] = {}
    for exp in experiments:
        study = exp["id"]
        for req in _eval_requests_for(exp, eval_persona):
            eval_contracts[study] |= _contract_lines(req["prompt"])
            eval_sample.setdefault(study, req["prompt"])

    print("\n" + "=" * 78)
    print("  IN-SAMPLE vs TRANSFER-ONLY  (does the SFT teach this study's eval task?")
    print("  answer SPACE compared; scenario paraphrasing is by-design and ignored)")
    print("=" * 78)

    def _classify(t_lines: set[str], e_lines: set[str]) -> tuple[str, str]:
        """Return (verdict, kind) comparing train vs eval answer SPACES.

        kind ∈ {ok, warn, transfer}. 'transfer' = the training task's answer space
        differs from the eval's, so SFT on this study adds ~no IN-SAMPLE signal
        toward its eval (it's a transfer test). NOT a mechanical break — at eval
        the model reads the eval prompt's answer space.
        """
        t = {_answer_space(x) for x in t_lines}
        e = {_answer_space(x) for x in e_lines}
        if t == e:
            return "✓ in-sample (answer space matches)", "ok"
        t_types = {s[0] for s in t}
        e_types = {s[0] for s in e}
        if t_types != e_types:
            return (f"↔ transfer-only — different elicitation "
                    f"({sorted(t_types)} vs {sorted(e_types)}); no in-sample signal", "transfer")
        if "enum" in t_types:
            t_card = sorted(len(s[1]) for s in t if s[0] == "enum")
            e_card = sorted(len(s[1]) for s in e if s[0] == "enum")
            if t_card != e_card:
                return (f"↔ transfer-only — different option set "
                        f"(cardinality {t_card} vs {e_card}); no in-sample signal", "transfer")
            # Same cardinality but different option strings (letters vs semantic):
            # _coerce bridges these by POSITION, correct only if option order aligns.
            return ("△ in-sample but order-dependent — letter↔semantic bridged by "
                    "_coerce ONLY if option order matches; verify order", "warn")
        if "int" in t_types:
            t_rng = {s[1:] for s in t if s[0] == "int"}
            e_rng = {s[1:] for s in e if s[0] == "int"}
            if t_rng != e_rng:
                return (f"↔ transfer-only — different integer range "
                        f"({sorted(t_rng)} vs {sorted(e_rng)})", "transfer")
        return "✓ in-sample (cosmetic gloss differs only; parser-compatible)", "ok"

    studies = sorted(set(train_contracts) | set(eval_contracts))
    transfer: list[str] = []
    warns: list[str] = []
    for study in studies:
        t, e = train_contracts.get(study, set()), eval_contracts.get(study, set())
        if not t:
            verdict, kind = "— no TRAIN examples (excluded from SFT; transfer-only)", "transfer"
        elif not e:
            verdict, kind = "— no EVAL prompts built", "skip"
        else:
            verdict, kind = _classify(t, e)
        if kind == "transfer":
            transfer.append(study)
        elif kind == "warn":
            warns.append(study)
        print(f"\n  [{study}]  {verdict}")
        if kind in ("transfer", "warn"):
            for ln in sorted(t):
                print(f"      TRAIN: {ln}")
            for ln in sorted(e):
                print(f"      EVAL : {ln}")
        if args.show_bodies and study in train_sample and study in eval_sample:
            print("      --- TRAIN prompt tail ---")
            for ln in train_sample[study].splitlines()[-6:]:
                print(f"        | {ln}")
            print("      --- EVAL prompt tail ---")
            for ln in eval_sample[study].splitlines()[-6:]:
                print(f"        | {ln}")

    print("\n" + "=" * 78)
    if transfer:
        print(f"  ↔ {len(transfer)} TRANSFER-ONLY study(ies): {', '.join(transfer)}")
        print("  Training teaches a different task/answer-space than the eval here, so")
        print("  grounding won't move these IN-SAMPLE — judge them as transfer, and do")
        print("  NOT use them as the in-sample mechanism gate (§8). Not a mechanical")
        print("  break: the model reads the eval prompt at eval time. (Watch the eval's")
        print("  per-study no-response rate for separate SFT-overfit collapse.)")
        if "dominator_neglect" in transfer:
            print("  • dominator_neglect is the current Phase-1 gate (§8) — it reads as a")
            print("    transfer/construct test, not clean in-sample grounding; consider a")
            print("    matched study (e.g. myside) for gate rule (b).")
    if warns:
        print(f"  △ {len(warns)} in-sample but order-dependent enum(s) to verify: {', '.join(warns)}")
    if not transfer and not warns:
        print("  ✓ All studies with training data are in-sample-compatible with eval.")
    print("=" * 78)
    sys.exit(0)


if __name__ == "__main__":
    main()
