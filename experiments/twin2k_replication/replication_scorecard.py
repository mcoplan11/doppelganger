#!/usr/bin/env python3
"""Replication scorecard: per Mega-Study effect, did the model reproduce it?

For each authored experiment, runs the standard analyzer to get significance +
direction, and classifies the outcome against the human effect:

  - Human REAL effect (|human_d| >= threshold):
        HIT   = model significant AND correct direction   (sensitivity)
        MISS  = model n.s. or wrong direction             (false negative)
  - Human NULL effect (|human_d| < threshold):
        OK    = model n.s.                                (specificity)
        FALSE+ = model significant                        (false positive)

Direction is ignored for studies whose entries set "direction_unverified": true
(e.g. obedient_*), where only significance/magnitude is meaningful.

Usage:
    python replication_scorecard.py \
        --results results/DIR1 results/DIR2 ... \
        --experiments experiments_megastudy.json experiments_hiring.json ...
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import sys

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from analysis import analyze_experiment  # noqa: E402


def find_rows(results_dirs, exp_id):
    for d in results_dirs:
        f = Path(d) / f"{exp_id}.json"
        if f.exists():
            return json.loads(f.read_text())
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", nargs="+", required=True)
    ap.add_argument("--experiments", nargs="+", required=True)
    ap.add_argument("--threshold", type=float, default=0.1,
                    help="|human d| below this is treated as a null effect")
    args = ap.parse_args()

    exps = []
    for ef in args.experiments:
        exps.extend(json.loads(Path(ef).read_text()))

    rows_out = []
    for e in exps:
        h = e.get("human_effect_size")
        if h is None:
            continue
        rows = find_rows(args.results, e["id"])
        if not rows:
            continue
        res = analyze_experiment(e, rows)
        sig = bool(res.get("significant"))
        correct = bool(res.get("correct_direction"))
        p = res.get("p_value")
        human_real = abs(h) >= args.threshold
        # obedient_* : direction not verifiable -> replication = significance only
        dir_unverified = "not verifiable" in (e.get("note", "").lower())
        replicated = sig and (correct or dir_unverified)
        if human_real:
            verdict = "HIT" if replicated else "MISS"
        else:
            verdict = "FALSE+" if sig else "ok"
        rows_out.append({
            "id": e["id"], "human_d": h, "human_real": human_real,
            "sig": sig, "correct_dir": correct, "p": p,
            "verdict": verdict,
        })

    # ---- table ----
    rows_out.sort(key=lambda r: (not r["human_real"], -abs(r["human_d"])))
    print(f"\n{'outcome':<34}{'human_d':>9}{'type':>7}{'model p':>10}{'dir':>5}{'verdict':>9}")
    print("-" * 74)
    for r in rows_out:
        pstr = "n/a" if r["p"] is None or r["p"] != r["p"] else f"{r['p']:.3g}"
        print(f"{r['id']:<34}{r['human_d']:>9.3f}{('real' if r['human_real'] else 'null'):>7}"
              f"{pstr:>10}{('ok' if r['correct_dir'] else 'x'):>5}{r['verdict']:>9}")

    real = [r for r in rows_out if r["human_real"]]
    null = [r for r in rows_out if not r["human_real"]]
    hits = sum(1 for r in real if r["verdict"] == "HIT")
    falsepos = sum(1 for r in null if r["verdict"] == "FALSE+")
    print("-" * 74)
    print(f"REAL human effects:  {len(real):>3}   replicated (HIT): {hits}   "
          f"missed: {len(real)-hits}"
          + (f"   sensitivity = {hits/len(real):.0%}" if real else ""))
    print(f"NULL human effects:  {len(null):>3}   correctly null:   {len(null)-falsepos}   "
          f"false positives: {falsepos}"
          + (f"   specificity = {(len(null)-falsepos)/len(null):.0%}" if null else ""))


if __name__ == "__main__":
    main()
